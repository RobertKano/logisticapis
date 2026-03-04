import os
import hashlib
import requests
import json
from datetime import datetime
from settings import CURRENT_STATE_FILE, HASH_FILE, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# Используем токены напрямую из настроек
tg_bot_token = TELEGRAM_TOKEN
raw_chat_ids = TELEGRAM_CHAT_ID

def send_tg_summary(report_json_path=CURRENT_STATE_FILE, force=False):
    """Шлет сводку по ГОТОВЫМ грузам, используя CURRENT_STATE_FILE"""
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

    # Ключевые слова-маркеры готовности
    READY_STATUSES = ["прибыл", "готов", "выдаче", "терминал", "хранение", "складе"]

    grouped_by_tk = {}
    ready_count = 0

    for item in active_items:
        status_text = str(item.get('status', '')).lower()
        sender = str(item.get('sender', '')).upper()
        route = str(item.get('route', '')).upper()
        tk = str(item.get('tk', ''))

        # Твои фильтры для водителя
        if "ЮЖНЫЙ ФОРПОСТ" in sender: continue

        # Проверка хвоста маршрута (Астрахань)
        route_parts = route.replace('➡️', '->').split('->')
        if "АСТРА" not in route_parts[-1]: continue

        # Исключаем БСД (по твоей просьбе)
        if "БСД" in tk: continue

        # Проверка готовности
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
                route_display = item['route'].replace('->', '➡️')
                p_raw = str(item.get('payment', '')).lower()
                is_paid = p_raw.startswith('оплаче') and 'к ' not in p_raw
                pay_icon = "✅" if is_paid else "⚠️"
                payment_info = "Оплачено" if is_paid else item.get('payment', '').upper()
                msg += (
                    f"  ├ **№{item['id']}**\n"
                    f"  ├ 🚛 _{item['sender']}_\n"
                    f"  ├ 📍 _{route_display}_\n"
                    f"  ├ ⚖️ _{item['params']}_\n"
                    f"  ├ {pay_icon} *{payment_info}*\n"
                    f"  └ 🏷 Статус: *{item['status']}*\n"
                )
            msg += "\n"
        msg += f"---\n_Всего к выдаче: **{ready_count}** шт._"

    # Хеширование контента (ID + оплата) для предотвращения спама
    content_to_hash = ""
    for tk in sorted(grouped_by_tk.keys()):
        for item in grouped_by_tk[tk]:
            content_to_hash += f"{item['id']}{item['payment']}"

    current_hash = hashlib.md5(content_to_hash.encode('utf-8')).hexdigest()

    # Проверка изменения состояния через HASH_FILE из настроек
    if not force and os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'r') as f:
            if f.read() == current_hash:
                print("[Notifier] Состав и оплата грузов не изменились. Пропуск.")
                return

    # Рассылка по чатам
    chat_ids = [cid.strip().replace('"', '').replace("'", "") for cid in raw_chat_ids.split(",") if cid.strip()]
    url = f"https://api.telegram.org/bot{tg_bot_token}/sendMessage"
    success_any = False

    for chat_id in chat_ids:
        if not chat_id: continue
        try:
            r = requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
            if r.status_code == 200:
                success_any = True
                print(f"[Notifier] Успешно отправлено в чат: {chat_id}")
            else:
                print(f"[Notifier] Ошибка API: {r.text}")
        except Exception as e:
            print(f"[Notifier] Ошибка связи с {chat_id}: {e}")

    if success_any:
        with open(HASH_FILE, 'w') as f:
            f.write(current_hash)

if __name__ == "__main__":
    print("\n[Test System] Запуск нотификатора...")
    print(f"[-] Файл отчета: {CURRENT_STATE_FILE}")
    # Принудительный тест
    send_tg_summary(CURRENT_STATE_FILE, force=True)
