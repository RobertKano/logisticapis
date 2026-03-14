import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


import json
import sqlite3
from src.settings import CURRENT_STATE_FILE, DATA_DIR
from flask import Flask, render_template, jsonify, send_from_directory, request
from src.database import CargoDB
app = Flask(__name__)
db = CargoDB()

# --- ЛОГИКА ОКРУЖЕНИЯ ---
IS_DEV_MODE = "--dev" in sys.argv
PORT = 5001 if IS_DEV_MODE else 5000

# Путь к документации (оставляем твой расчет)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_PATH = os.path.join(BASE_DIR, 'docs', 'build', 'html')

def get_latest_report():
    """Читает всегда актуальное состояние из current_state.json"""
    # Нам больше не нужно проверять IS_DEV_MODE для выбора файла,
    # так как main_parser теперь всегда пишет в CURRENT_STATE_FILE
    file_path = CURRENT_STATE_FILE

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Error] Ошибка чтения JSON: {e}")
            return None

    print(f"[Debug] Файл не найден: {file_path}")
    return None

def get_report_from_db():
    """Собирает структуру отчета напрямую из SQLite"""
    try:
        conn = db.get_connection()
        # Ставим row_factory, чтобы получать данные как словари (dict)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Загружаем АКТИВ (is_archived = 0)
        cursor.execute("""
            SELECT *,
            (places || 'М | ' || weight || 'КГ | ' || volume || 'М3') as params
            FROM cargo
            WHERE is_archived = 0
            ORDER BY arrival ASC
        """)
        active = [dict(row) for row in cursor.fetchall()]

        # 2. Загружаем АРХИВ (is_archived = 1)
        cursor.execute("""
            SELECT *,
            (places || 'М | ' || weight || 'КГ | ' || volume || 'М3') as params
            FROM cargo
            WHERE is_archived = 1
            ORDER BY updated_at DESC LIMIT 200
        """)
        archive = [dict(row) for row in cursor.fetchall()]

        # 3. Формируем метаданные
        # Время последнего обновления берем из самой свежей записи
        cursor.execute("SELECT MAX(updated_at) FROM cargo")
        last_update = cursor.fetchone()[0] or "Н/Д"

        return {
            "metadata": {
                "created_at": last_update,
                "active_count": len(active),
                "archive_count": len(archive)
            },
            "active": active,
            "archive": archive
        }
    except Exception as e:
        print(f"[Server DB Error] {e}")
        return None
    finally:
        conn.close()


@app.route('/api/analytics')
def api_analytics():
    try:
        conn = db.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. ОБЩАЯ СВОДКА (Карточки сверху)
        # Учитываем всё, где участвует "ЮЖНЫЙ ФОРПОСТ" и груз активен
        cursor.execute("""
            SELECT
                SUM(places) as total_places,
                ROUND(SUM(weight), 1) as total_weight,
                ROUND(SUM(volume), 2) as total_volume,
                ROUND(SUM(total_price), 2) as total_unpaid
            FROM cargo
            WHERE is_archived = 0
              AND (sender LIKE '%ЮЖНЫЙ ФОРПОСТ%' OR recipient LIKE '%ЮЖНЫЙ ФОРПОСТ%')
        """)
        summary = dict(cursor.fetchone())

        return jsonify({
            "status": "ok",
            "summary": summary
        })
    except Exception as e:
        print(f"[Analytics Summary Error] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/analytics/tk-compare')
def api_tk_compare():
    days = request.args.get('days', 30)
    try:
        conn = db.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Тянем сырые данные для точного расчета
        cursor.execute(f"""
            SELECT
                tk,
                CASE
                    WHEN weight <= 15 THEN '📦 Ультра-малые (до 15кг)'
                    WHEN weight > 15 AND weight <= 35 THEN '📦 Малые (15-35кг)'
                    WHEN weight > 35 AND weight <= 75 THEN '📦 Средние (35-75кг)'
                    WHEN weight > 75 AND weight <= 150 THEN '📦 Премиум (75-150кг)'
                    WHEN weight > 150 AND weight <= 400 THEN '🚚 Крупные (150-400кг)'
                    WHEN weight > 400 AND weight <= 1000 THEN '🚚 Тяжелые (400кг-1т)'
                    ELSE '🚜 Тонники (свыше 1т)'
                END as category,
                total_price,
                weight,
                volume,
                places,
                ABS(JULIANDAY(COALESCE(archived_at, date('now'))) - JULIANDAY(created_at)) as days_diff
            FROM cargo
            WHERE updated_at >= date('now', '-{days} days')
              AND (sender LIKE '%ЮЖНЫЙ ФОРПОСТ%' OR recipient LIKE '%ЮЖНЫЙ ФОРПОСТ%')

              -- ВОТ ЭТА СТРОКА ОТСЕКАЕТ АНОМАЛИИ (Грузы тяжелее 5 тонн):
              AND weight > 0 AND weight < 5000

              AND total_price > 0
        """)

        raw_rows = [dict(row) for row in cursor.fetchall()]

        # 2. Группируем данные в Python
        stats_map = {}
        for r in raw_rows:
            key = (r['tk'], r['category'])
            if key not in stats_map:
                stats_map[key] = {
                    'prices_kg': [], 'days': [],
                    'total_spent': 0, 'total_weight': 0,
                    'total_vol': 0, 'total_places': 0
                }

            stats_map[key]['prices_kg'].append(r['total_price'] / r['weight'])
            stats_map[key]['days'].append(r['days_diff'])
            stats_map[key]['total_spent'] += r['total_price']
            stats_map[key]['total_weight'] += r['weight']
            stats_map[key]['total_vol'] += r['volume']
            stats_map[key]['total_places'] += r['places']

        final_stats = []
        for (tk, cat), data in stats_map.items():
            # Работаем через NumPy для квантилей
            prices = np.array(data['prices_kg'])

            # Расчет квантилей (25, 50, 75)
            q25 = np.percentile(prices, 25)
            q50 = np.median(prices)  # МЕДИАНА (Типичный тариф)
            q75 = np.percentile(prices, 75)

            efficiency_score = data['total_weight'] / data['total_spent'] if data['total_spent'] > 0 else 0

            final_stats.append({
                "tk": tk,
                "category": cat,
                "total_shipments": len(prices),
                "avg_days": round(np.mean(data['days']), 1),
                "cost_per_kg": round(q50, 2),  # Основная цифра в таблице
                "q25_kg": round(q25, 2),       # Минимум "нормы"
                "q75_kg": round(q75, 2),       # Максимум "нормы"
                "cost_per_m3": round(data['total_spent'] / data['total_vol'], 0) if data['total_vol'] > 0 else 0,
                "sum_places": data['total_places'],
                "sum_weight": round(data['total_weight'], 1),
                "sum_volume": round(data['total_vol'], 2),
                "total_spent": round(data['total_spent'], 2),
                "efficiency_index": round(efficiency_score, 4)
            })

        return jsonify(final_stats)
    except Exception as e:
        print(f"❌ [Analytics Error]: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
# --- РОУТЫ ---
@app.route('/')
def index():
    report_data = get_report_from_db() # Теперь из базы!
    if report_data:
        return render_template('index.html', report=report_data, is_dev=IS_DEV_MODE)
    return "Ошибка: База данных пуста или недоступна."


@app.route('/api/latest')
def api_latest():
    report_data = get_report_from_db()
    if report_data:
        return jsonify(report_data)
    return jsonify({"status": "error"}), 404


@app.route('/analytics')
def analytics_page():
    # Мы можем передать туда IS_DEV_MODE, чтобы сохранить стиль
    return render_template('analytics.html', is_dev=IS_DEV_MODE)


@app.route('/docs/')
@app.route('/docs/<path:filename>')
def render_docs(filename='index.html'):
    return send_from_directory(DOCS_PATH, filename)

# --- РОУТЫ ДЛЯ ЗАДАЧ ВОДИТЕЛЯ (PLANNER) ---
@app.route('/api/tasks', methods=['GET', 'POST'])
def handle_tasks_root():
    conn = db.get_connection()
    try:
        if request.method == 'POST':
            data = request.json
            cursor = conn.cursor()
            # 11 полей - 11 знаков вопроса
            cursor.execute("""
                INSERT INTO driver_tasks (
                    task_date, task_time, title, description,
                    address, contact_info, cargo_id, payment_amount,
                    payment_type, priority, is_completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('task_date'),
                data.get('task_time', '09:00'),
                data.get('title'),
                data.get('description', ''),
                data.get('address', ''),
                data.get('contact_info', ''),
                data.get('cargo_id', ''),
                float(data.get('payment_amount') or 0.0),
                data.get('payment_type', 'none'),
                int(data.get('priority', 1)),
                int(data.get('is_completed', 0))
            ))
            conn.commit()
            return jsonify({"status": "ok", "id": cursor.lastrowid})

        # GET логика
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM driver_tasks WHERE task_date >= date('now', '-1 day') ORDER BY task_date, task_time")
        return jsonify([dict(row) for row in cursor.fetchall()])
    except Exception as e:
        print(f"❌ [API Tasks Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'PATCH', 'DELETE'])
def manage_single_task(task_id):
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        if request.method == 'DELETE':
            cursor.execute("DELETE FROM driver_tasks WHERE id = ?", (task_id,))

        elif request.method == 'PUT':
            data = request.json
            # Здесь обновляем 10 полей по ID
            cursor.execute("""
                UPDATE driver_tasks SET
                task_date=?, task_time=?, title=?, description=?,
                address=?, contact_info=?, payment_amount=?, payment_type=?,
                priority=?, is_completed=?
                WHERE id=?
            """, (
                data['task_date'], data['task_time'], data['title'],
                data.get('description', ''), data.get('address', ''),
                data.get('contact_info', ''), float(data.get('payment_amount') or 0.0),
                data.get('payment_type', 'none'), int(data.get('priority', 1)),
                int(data.get('is_completed', 0)), task_id
            ))

        elif request.method == 'PATCH':
            data = request.json
            if 'is_completed' in data:
                cursor.execute("UPDATE driver_tasks SET is_completed = ? WHERE id = ?",
                               (int(data['is_completed']), task_id))

        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"❌ [API Task Manage Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route('/planner')
def planner_page():
    """Рендеринг страницы планировщика"""
    return render_template('planner.html', is_dev=IS_DEV_MODE)



if __name__ == '__main__':
    mode_name = "DEVELOPMENT" if IS_DEV_MODE else "PRODUCTION"
    print(f"[{mode_name}] Сервер запущен: http://0.0.0.0:{PORT}")
    # В проде debug должен быть False
    app.run(debug=IS_DEV_MODE, host='0.0.0.0', port=PORT)
