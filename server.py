from flask import Flask, render_template, jsonify, send_from_directory, request
import json
import os
import sys
from datetime import datetime

app = Flask(__name__)

# --- ЛОГИКА ОКРУЖЕНИЯ ---
IS_DEV_MODE = "--dev" in sys.argv
PORT = 5001 if IS_DEV_MODE else 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DOCS_PATH = os.path.join(BASE_DIR, 'docs', 'build', 'html')
MANUAL_FILE = os.path.join(DATA_DIR, 'manual_cargo.json')

# --- ФУНКЦИИ ДАННЫХ ---
def get_manual_data():
    """Загружает памятки (только для DEV)."""
    if IS_DEV_MODE and os.path.exists(MANUAL_FILE):
        try:
            with open(MANUAL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def get_latest_report():
    date_str = datetime.now().strftime('%Y-%m-%d')
    # Убедись, что этот файл РЕАЛЬНО существует в папке data
    filename = "test_all_tk_processed.json" if IS_DEV_MODE else f"report_{date_str}.json"
    file_path = os.path.join(DATA_DIR, filename)

    print(f"[Debug] Путь к файлу: {file_path}") # Добавь этот принт для теста

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# --- РОУТЫ ---
@app.route('/')
def index():
    report_data = get_latest_report()
    if report_data:
        # Передаем флаг is_dev в шаблон
        return render_template('index.html', report=report_data, is_dev=IS_DEV_MODE)
    return "Ошибка: отчет не найден."

@app.route('/api/latest')
def api_latest():
    report_data = get_latest_report()
    manual_items = get_manual_data()

    if report_data:
        # Если есть памятки, подмешиваем их в начало списка active
        if manual_items:
            for item in manual_items:
                item['is_manual'] = True
                if 'tk' not in item: item['tk'] = "📝 ПАМЯТКА"
            report_data['active'] = manual_items + report_data['active']
        return jsonify(report_data)
    return jsonify({"status": "error"}), 404

# --- АДМИН-МЕТОДЫ (только для DEV) ---
@app.route('/admin/add-manual', methods=['POST'])
def add_manual():
    if not IS_DEV_MODE: return jsonify({"error": "Forbidden"}), 403
    data = get_manual_data()
    data.append(request.json)
    with open(MANUAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return jsonify({"status": "ok"})

@app.route('/admin/delete-manual/<cargo_id>', methods=['DELETE'])
def delete_manual(cargo_id):
    if not IS_DEV_MODE: return jsonify({"error": "Forbidden"}), 403
    data = [i for i in get_manual_data() if str(i.get('id')) != str(cargo_id)]
    with open(MANUAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return jsonify({"status": "ok"})

@app.route('/admin/update-manual', methods=['POST'])
def update_manual():
    if not IS_DEV_MODE:
        return jsonify({'error': 'Forbidden'}), 403

    updated_item = request.json
    data = get_manual_data()

    new_data = [updated_item if str(item.get('id')) == str(updated_item.get('id')) else item for item in data]

    with open(MANUAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)

    return jsonify({"status": "ok"})

@app.route('/docs/')
@app.route('/docs/<path:filename>')
def render_docs(filename='index.html'):
    return send_from_directory(DOCS_PATH, filename)

if __name__ == '__main__':
    mode_name = "DEVELOPMENT" if IS_DEV_MODE else "PRODUCTION"
    print(f"[{mode_name}] Сервер запущен: http://0.0.0.0:{PORT}")
    app.run(debug=IS_DEV_MODE, host='0.0.0.0', port=PORT)
