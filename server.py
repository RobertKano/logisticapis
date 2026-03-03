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

    if report_data:
        return jsonify(report_data)
    return jsonify({"status": "error"}), 404


@app.route('/docs/')
@app.route('/docs/<path:filename>')
def render_docs(filename='index.html'):
    return send_from_directory(DOCS_PATH, filename)

if __name__ == '__main__':
    mode_name = "DEVELOPMENT" if IS_DEV_MODE else "PRODUCTION"
    print(f"[{mode_name}] Сервер запущен: http://0.0.0.0:{PORT}")
    app.run(debug=IS_DEV_MODE, host='0.0.0.0', port=PORT)
