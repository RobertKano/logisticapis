import os
import hashlib
import requests
import json
# from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

import settings as st

# Загрузка переменных окружения
load_dotenv()

tg_bot_token = st.TELEGRAM_TOKEN
raw_chat_ids = st.TELEGRAM_CHAT_ID


def send_tg_summary(report_json_path, force=False):
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
        sender = str(item.get('sender', '')).upper()
        route = str(item.get('route', '')).upper()

        # 1. УСЛОВИЯ ИСКЛЮЧЕНИЯ (Фильтры для водителя)
        # Исключаем "Южный Форпост"
        if "ЮЖНЫЙ ФОРПОСТ" in sender:
            continue

        # Исключаем всё, что едет НЕ в Астрахань (проверяем хвост маршрута)
        # "route": "АСТРА -> ПЕНЗА"
        if "АСТРА" not in route.split('->')[-1] and "АСТРА" not in route.split('➡️')[-1]:
            continue

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
                p_raw = str(item.get('payment', '')).lower()
                is_paid = p_raw.startswith('оплаче') and 'к ' not in p_raw
                pay_icon = "✅" if is_paid else "⚠️"
                payment_info = "Оплачено" if is_paid else item.get('payment', '').upper()
                msg += (
                    f"  ├ **№{item['id']}**\n"
                    f"  ├ 🚛 _{item['sender']}_\n"
                    f"  ├ 📍 _{route}_\n"
                    f"  ├ ⚖️ _{item['params']}_\n"
                    f"  ├ {pay_icon} *{payment_info}*\n" # Новая строка с оплатой
                    f"  └ 🏷 Статус: *{item['status']}*\n"
                )
            msg += "\n"

        msg += f"---"
        msg += f"\n_Всего к выдаче: **{ready_count}** шт._"

    # 1. Собираем только значимые данные для хеша (ID + статус оплаты)
    content_to_hash = ""
    for tk in sorted(grouped_by_tk.keys()):
        for item in grouped_by_tk[tk]:
            content_to_hash += f"{item['id']}{item['payment']}"

    # 2. Проверяем хеш именно контента, а не всего сообщения
    current_hash = hashlib.md5(content_to_hash.encode('utf-8')).hexdigest()

    if not force and os.path.exists(st.HASH_FILE):
        with open(st.HASH_FILE, 'r') as f:
            if f.read() == current_hash:
                print("[Notifier] Состав и оплата грузов не изменились. Пропуск.")
                return
    if force:
        print("[Test] Включен режим принудительной отправки (игнорируем хеш).")


    # Отправка в Telegram
    chat_ids = [cid.strip() for cid in raw_chat_ids.split(",") if cid.strip()]
    url = f"https://api.telegram.org/bot{tg_bot_token}/sendMessage"
    success_any = False

    for chat_id in chat_ids:
        chat_id = chat_id.strip().replace('"', '').replace("'", "") # Чистим от мусора
        if not chat_id: continue
        print(f"[Debug] Пробую отправить в ID: '{chat_id}'")
        payload = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }

        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                success_any = True
                print(f"[Notifier] Успешно отправлено в чат: {chat_id}")
            else:
                print(f"[Notifier] Ошибка API Telegram для {chat_id}: {r.text}")
        except Exception as e:
            print(f"[Notifier] Ошибка связи при отправке в {chat_id}: {e}")

    if success_any:
        with open(st.HASH_FILE, 'w') as f:
            f.write(current_hash)

if __name__ == "__main__":
    date_str = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(os.path.dirname(__file__), '..', 'data', f'report_{date_str}.json')
    print("\n[Test System] Запуск нотификатора...")
    print(f"[-] Файл отчета: {path}")
    print(f"[-] Целевые чаты: {os.getenv('TG_CHAT_ID')}")
    send_tg_summary(path, force=True)
    print("[Test System] Тест завершен.\n")
