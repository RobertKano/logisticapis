import os
import hashlib
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

import settings as st

# Загрузка переменных окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
# Путь к файлу хеша, чтобы не спамить
# st.HASH_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'last_report_hash.txt')

def send_tg_summary(report_json_path):
    """Читает отчет и шлет детализированную сводку только по ГОТОВЫМ грузам"""
    if not os.path.exists(report_json_path):
        print(f"[Notifier] Файл отчета не найден: {report_json_path}")
        return

    try:
        with open(report_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Notifier] Ошибка чтения JSON: {e}")
        return

    active_items = data.get("active", [])

    # Ключевые слова-маркеры готовности груза к выдаче
    READY_STATUSES = ["прибыл", "готов", "выдаче", "терминал", "хранение", "складе"]

    # Фильтруем и группируем только то, что реально можно забрать
    grouped_by_tk = {}
    ready_count = 0

    for item in active_items:
        status_text = str(item.get('status', '')).lower()

        # Проверка: должен ли водитель видеть этот груз
        if any(word in status_text for word in READY_STATUSES):
            tk_name = item['tk']
            if tk_name not in grouped_by_tk:
                grouped_by_tk[tk_name] = []
            grouped_by_tk[tk_name].append(item)
            ready_count += 1

    # Формируем текст сообщения
    if not grouped_by_tk:
        msg = "🚚 **Сводка ТК:** Грузов, готовых к выдаче, на данный момент нет."
    else:
        report_time = data.get("metadata", {}).get("created_at", datetime.now().strftime('%d.%m.%Y %H:%M'))
        msg = f"✅ **Грузы ГОТОВЫ к забору** ({report_time}):\n\n"

        for tk_name, items in grouped_by_tk.items():
            msg += f"📦 **{tk_name}**:\n"
            for item in items:
                # Заменяем стрелочку на более наглядную для мобилки
                route = item['route'].replace('->', '➡️')
                msg += (
                    f"  ├ **№{item['id']}**\n"
                    f"  ├    _{item['sender']}_\n"
                    f"  ├ 📍 _{route}_\n"
                    f"  ├ ⚖️ _{item['params']}_\n"
                    f"  └ 🏷 Статус: *{item['status']}*\n"
                )
            msg += "\n"

        msg += f"---"
        msg += f"\n_Всего к выдаче: **{ready_count}** шт._"

    # Защита от дублей: проверяем, изменился ли текст сообщения
    current_hash = hashlib.md5(msg.encode('utf-8')).hexdigest()
    if os.path.exists(st.HASH_FILE):
        with open(st.HASH_FILE, 'r') as f:
            if f.read() == current_hash:
                print("[Notifier] Состав готовых грузов не изменился. Пропуск отправки.")
                return

    # Отправка в Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            with open(st.HASH_FILE, 'w') as f:
                f.write(current_hash)
            print(f"[Notifier] Сводка ({ready_count} шт.) отправлена в Telegram.")
        else:
            print(f"[Notifier] Ошибка API Telegram: {r.text}")
    except Exception as e:
        print(f"[Notifier] Ошибка при отправке запроса: {e}")

if __name__ == "__main__":
    # Код для самостоятельного запуска модуля (тест)
    date_str = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(os.path.dirname(__file__), '..', 'data', f'report_{date_str}.json')
    print(f"[Test] Запуск нотификатора для файла: {path}")
    send_tg_summary(path)
