import os
import sys


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

        # 1. Сводка по ТК (Вес, Цена, Цена за кг)
        cursor.execute("""
            SELECT
                SUM(places) as total_places,
                ROUND(SUM(weight), 1) as total_weight,
                ROUND(SUM(volume), 2) as total_volume,
                ROUND(SUM(total_price), 2) as total_unpaid
            FROM cargo
            WHERE is_archived = 0
              AND payer_type = 'recipient' -- УЧИТЫВАЕМ ТОЛЬКО НАС
        """)
        tk_stats = [dict(row) for row in cursor.fetchall()]

        # 2. Общие показатели склада (только актив)
        cursor.execute("""
            SELECT
                SUM(places) as total_places,
                ROUND(SUM(weight), 1) as total_weight,
                ROUND(SUM(volume), 2) as total_volume,
                ROUND(SUM(total_price), 2) as total_unpaid
            FROM cargo WHERE is_archived = 0
        """)
        summary = dict(cursor.fetchone())

        return jsonify({
            "status": "ok",
            "tk_stats": tk_stats,
            "summary": summary
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/analytics/tk-compare')
def api_tk_compare():
    try:
        conn = db.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # ОБНОВЛЕННЫЙ ЗАПРОС: Считаем сроки от даты создания (created_at)
        cursor.execute("""
            SELECT
                tk,
                COUNT(id) as total_shipments,

                -- 1. СРОК: Разница между прибытием и первым появлением в базе
                -- ABS гарантирует отсутствие минусов, а COALESCE подстрахует от пустых дат
                ROUND(AVG(ABS(JULIANDAY(arrival) - JULIANDAY(COALESCE(created_at, updated_at)))), 1) as avg_days,

                -- 2. ОБЪЕМНЫЙ ВЕС (Коэффициент 250)
                ROUND(SUM(volume * 250), 0) as volume_weight,

                -- 3. ВЕС К ОПЛАТЕ (Максимум по каждой строке)
                ROUND(SUM(CASE WHEN weight > (volume * 250) THEN weight ELSE (volume * 250) END), 0) as pay_weight,

                -- 4. СТОИМОСТЬ ЗА КГ (От веса к оплате)
                ROUND(SUM(total_price) / NULLIF(SUM(CASE WHEN weight > (volume * 250) THEN weight ELSE (volume * 250) END), 0), 2) as cost_per_kg,

                -- 5. СТОИМОСТЬ ЗА МЕСТО
                ROUND(SUM(total_price) / NULLIF(SUM(places), 0), 2) as cost_per_place,

                ROUND(SUM(total_price), 2) as total_spent
            FROM cargo
            WHERE updated_at >= date('now', '-30 days')
              AND payer_type = 'recipient'
            GROUP BY tk
            ORDER BY total_spent DESC
        """)

        stats = [dict(row) for row in cursor.fetchall()]
        return jsonify(stats)
    except Exception as e:
        print(f"[Analytics Error] {e}")
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


if __name__ == '__main__':
    mode_name = "DEVELOPMENT" if IS_DEV_MODE else "PRODUCTION"
    print(f"[{mode_name}] Сервер запущен: http://0.0.0.0:{PORT}")
    # В проде debug должен быть False
    app.run(debug=IS_DEV_MODE, host='0.0.0.0', port=PORT)
