from flask import Flask, render_template, jsonify, send_from_directory
import json
import os
from datetime import datetime

# Инициализируем Flask приложение
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DOCS_PATH = os.path.join(BASE_DIR, 'docs', 'build', 'html')

def get_latest_report():
    """Загружает самый свежий JSON-отчет."""
    # Мы используем отчет за ТЕКУЩУЮ дату, которую сгенерировал main_parser.py
    date_str = datetime.now().strftime('%Y-%m-%d')
    file_path = os.path.join(DATA_DIR, f"report_{date_str}.json")

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Ошибка чтения JSON файла: {file_path}")
            return None
    return None

@app.route('/')
def index():
    """Главная страница с HTML-таблицей."""
    report_data = get_latest_report()
    if report_data:
        return render_template('index.html', report=report_data)
    else:
        return "Ошибка: отчет за сегодня не найден. Запустите main_parser.py"

@app.route('/api/latest')
def api_latest():
    """API-эндпоинт для чистого JSON."""
    report_data = get_latest_report()
    if report_data:
        return jsonify(report_data)
    else:
        return jsonify({"status": "error", "message": "Report not found"}), 404

@app.route('/docs/')
@app.route('/docs/<path:filename>')
def render_docs(filename='index.html'):
    """Отдает файлы документации Sphinx."""
    return send_from_directory(DOCS_PATH, filename)


if __name__ == '__main__':
    # Запуск локально на стандартном порту 5000
    print("Сервер запущен. Просмотр отчета: http://localhost:5000")
    print("API endpoint: http://localhost:5000/api/latest")
    print("Документация доступна по адресу: http://localhost:5000/docs/")
    app.run(debug=True, host='0.0.0.0', port=5000)
    # 192.168.0.96

