# -*- coding: utf-8 -*-
# Copyright (C) 2024-2026 RobertKano
# Project: LogisticAPIs (https://github.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org>.


import time
import json
import os
import re
from datetime import datetime

import settings as st


def cleanup_old_reports(data_dir, days=14):
    """Удаляет отчеты старше N дней, чтобы не захламлять диск"""
    if not os.path.exists(data_dir):
        return

    now = time.time()
    cutoff = now - (days * 86400) # 86400 секунд в сутках
    deleted_count = 0

    for f in os.listdir(data_dir):
        # Маска файла: строго report_YYYY-MM-DD.json
        if f.startswith("report_") and f.endswith(".json"):
            file_path = os.path.join(data_dir, f)
            try:
                # Проверяем дату последнего изменения
                if os.stat(file_path).st_mtime < cutoff:
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                print(f"[Cleanup] Ошибка при удалении {f}: {e}")

    if deleted_count > 0:
        print(f"[Cleanup] Очистка завершена. Удалено старых отчетов: {deleted_count}")


def update_permanent_archive(new_archive_items):
    """Сохраняет уникальные завершенные заказы в вечный архив, дополняя его"""
    if not new_archive_items:
        return

    # 1. Читаем существующий архив максимально безопасно
    old_history = []
    if os.path.exists(st.HISTORY_FILE):
        try:
            with open(st.HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    old_history = json.loads(content)
        except Exception as e:
            print(f"[Archive Error] Ошибка чтения файла истории: {e}")
            old_history = []

    # 2. Создаем набор существующих ID для мгновенной проверки
    existing_ids = {str(item.get('id')) for item in old_history if item.get('id')}

    # 3. Добавляем только те, которых реально нет в базе
    added_count = 0
    for item in new_archive_items:
        cargo_id = str(item.get('id', ''))

        # Если ID пустой (такого быть не должно) или уже есть в базе - пропускаем
        if not cargo_id or cargo_id in existing_ids:
            continue

        # Добавляем технические поля
        item['archived_at'] = datetime.now().strftime('%d.%m.%Y')
        if 'tk' not in item and item.get('is_manual'):
            item['tk'] = "📝 ПАМЯТКА"

        old_history.append(item)
        existing_ids.add(cargo_id)
        added_count += 1

    # 4. Сохраняем ВЕСЬ обновленный список обратно
    if added_count > 0:
        try:
            with open(st.HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(old_history, f, ensure_ascii=False, indent=4)
            print(f"[Archive] Успешно добавлено новых записей: {added_count}. Всего в архиве: {len(old_history)}")
        except Exception as e:
            print(f"[Archive Error] Критическая ошибка при записи истории: {e}")


def clean_name(text, is_city=False):
    if not text or not isinstance(text, str): return "???"

    # 1. Базовая очистка: убираем лишние символы и кавычки СРАЗУ
    cleaned = text.replace('"', '').replace('«', '').replace('»', '').replace("'", "")
    cleaned = re.sub(r'\(.*?\)', '', cleaned).lower()

    if is_city:
        # Убираем стандартные приставки
        city_trash = ["г. ", "город ", "пгт. ", "поселок ", "область", "обл.", " край", " р-н", " мо", " г "]
        for trash in city_trash:
            cleaned = cleaned.replace(trash, "")

        # Сокращаем терминалы и стороны света
        city_replacements = {
            "восток": "ВСТ", "запад": "ЗПД", "север": "СЕВ", "юг": "ЮГ",
            "терминал": "ТЕРМ", "склад": "СКЛ", "центральный": "ЦЕНТР",
            "юго-запад": "Ю-З", "северо-восток": "С-В"
        }
        for long, short in city_replacements.items():
            cleaned = cleaned.replace(long, short)

        # Маппинг городов из settings.py (Астрахань -> АСТРА и т.д.)
        for full, short in st.CITY_MAP.items():
            if full in cleaned:
                cleaned = cleaned.replace(full, short)
    else:
        # 2. Сокращаем организационные формы
        org_replacements = {
            "общество с ограниченной ответственностью": "ООО",
            "индивидуальный предприниматель": "ИП",
            "акционерное общество": "АО",
            "публичное акционерное общество": "ПАО",
            "торговый дом": "ТД",
            "группа компаний": "ГК",
            "производственное объединение": "ПО"
        }
        for long, short in org_replacements.items():
            cleaned = cleaned.replace(long, short)

        # 3. Чистим "информационный шум" в именах компаний
        # (Убираем слова, которые мешают быстрому поиску)
        noise_words = ["компания", "корпорация", "предприятие", "лтд", "ltd"]
        for word in noise_words:
            cleaned = re.sub(rf'\b{word}\b', '', cleaned)

    # Финальная сборка: убираем лишние пробелы и в UPPER CASE
    return " ".join(cleaned.split()).strip().upper()


# --- ОБРАБОТЧИКИ ТК ---

def parse_baikal(data):
    # Если пришел не список или список пуст — возвращаем пустой список результатов
    if not data or not isinstance(data, list):
        return []

    results = []
    for order in data:
        # Проверяем, не заглушка ли это (на всякий случай)
        if order.get("status") == "empty":
            continue

        cargo_list = order.get("cargoList", [])
        if not cargo_list: continue

        first_item = cargo_list[0]
        consignor = first_item.get("consignor", {})
        consignee = first_item.get("consignee", {})

        services = first_item.get("services", [])
        payer_data = services[0].get("payer", {}) if services else {}
        payer_inn = payer_data.get("inn")

        if payer_inn == consignee.get("inn"):
            payer_type = "recipient"
        elif payer_inn == consignor.get("inn"):
            payer_type = "sender"
        else:
            payer_type = "third_party"

        # Считаем параметры
        places = sum(int(item.get("cargo", {}).get("places") or 0) for item in cargo_list)
        weight = sum(float(item.get("cargo", {}).get("weight") or 0) for item in cargo_list)
        volume = sum(float(item.get("cargo", {}).get("volume") or 0) for item in cargo_list)

        # расчет долга и оплаты
        total = order.get("total") or first_item.get("total", {})
        total_sum = float(total.get("sum") or 0)
        total_paid = float(total.get("paid") or 0)
        debt = round(total_sum - total_paid, 2)

        if debt > 0:
            payment_status = f"К ОПЛАТЕ: {debt}"
        else:
            payment_status = order.get("paidStatus") or "Н/Д"

        results.append({
            "tk": "Байкал Сервис",
            "id": order.get("tracking") or "Н/Д",
            "sender": clean_name(consignor.get("name")),
            "recipient": clean_name(consignee.get("name")),
            "payer_type": payer_type,
            "status": order.get("orderstatus", "Н/Д"),
            "params": f"{places}м | {weight}кг | {volume}м3",
            "arrival": first_item.get('dateArrivalPlane') or order.get('dateArrivalPlane'),
            "payment": payment_status,
            "route": f"{clean_name(first_item.get('departure', {}).get('name'), True)} ➡️ {clean_name(first_item.get('destination', {}).get('name'), True)}"
        })
    return results

def parse_dellin(data):
    results = []
    for o in data.get("orders", []):
        # 1. Извлекаем основной документ (накладную)
        docs = o.get("documents", [])
        main_doc = docs[0] if docs else {}

        f = o.get("freight", {})
        sender_data = o.get("sender", {})
        receiver_data = o.get("receiver", {})
        payer_data = o.get("payer", {})

        # --- ЛОГИКА ОПРЕДЕЛЕНИЯ СТАТУСА ОПЛАТЫ ---
        # У ДЛ есть поле isPaid в корне, но долг точнее в main_doc
        debt = float(main_doc.get("debtSum") or 0)
        is_paid_root = o.get("isPaid", False)

        if debt > 0:
            payment_status = f"К ОПЛАТЕ: {debt}"
        elif is_paid_root:
            payment_status = "Оплачено"
        else:
            # Если долг 0, но флаг isPaid=False — значит, счет еще не закрыт (ждем проводку)
            total_sum = main_doc.get("totalSum") or o.get("totalSum", "Н/Д")
            payment_status = f"К ОПЛАТЕ: {total_sum}"
        # ------------------------------------------

        p_inn = payer_data.get("inn")
        r_inn = receiver_data.get("inn")

        if p_inn and r_inn and p_inn == r_inn:
            payer_type = "recipient"
        elif p_inn and p_inn == sender_data.get("inn"):
            payer_type = "sender"
        else:
            payer_type = "third_party"

        results.append({
            "tk": "Деловые Линии",
            "id": o.get("orderId"),
            "sender": clean_name(sender_data.get("name")),
            "recipient": clean_name(receiver_data.get("name")),
            "payer_type": payer_type,
            "status": f"{o.get('stateName')} ({o.get('progressPercent')}%)",
            "params": f"{f.get('places')}м | {f.get('weight')}кг | {f.get('volume')}м3",
            "arrival": o.get("orderDates", {}).get("arrivalToOspReceiver"),
            "payment": payment_status, # ЗАМЕНЕНО
            "route": f"{clean_name(o.get('derival', {}).get('terminalCity') or o.get('derival', {}).get('city'), True)} ➡️ {clean_name(o.get('arrival', {}).get('terminalCity') or o.get('arrival', {}).get('city'), True)}"
        })
    return results



def parse_pecom(data):
    results = []
    for i in data.get("cargos", []):
        c = i.get("cargo", {})
        info = i.get("info", {})
        services = i.get("services", {})
        service_items = services.get("items", [])

        # 1. СУММАРНЫЙ ДОЛГ (главный показатель)
        total_debt = float(services.get("debt", 0))

        # 2. ПРОВЕРКА ПО ВСЕМ УСЛУГАМ (через any)
        # Ищем, есть ли хоть одна услуга, которую ПЭК пометил как "к оплате при получении"
        has_unpaid_service = any(s.get("payToReceive") is True for s in service_items)

        # Итоговая логика статуса оплаты:
        if total_debt <= 0 and not has_unpaid_service:
            payment_status = "Оплачено"
        elif total_debt > 0 and not has_unpaid_service:
            # Кейс, когда долг есть, но он "не блокирующий" (редко, но бывает)
            payment_status = f"Долг: {total_debt}"
        else:
            # Самый критичный случай: есть услуги, помеченные "к оплате"
            payment_status = f"К ОПЛАТЕ: {total_debt}"

        # ... (логика payer_type остается прежней) ...
        # Используем .all() для определения payer_type, если хотим быть уверенными,
        # что плательщик везде один и тот же (обычно это так)
        p_types = [s.get("payerType") for s in service_items]
        if all(pt == 2 for pt in p_types):
            payer_type = "recipient"
        elif all(pt == 1 for pt in p_types):
            payer_type = "sender"
        else:
            payer_type = "mixed/third_party"

        results.append({
            "tk": "ПЭК",
            "id": c.get("cargoBarCode"),
            "sender": clean_name(i.get("sender", {}).get("sender")),
            "recipient": clean_name(i.get("receiver", {}).get("receiver")),
            "payer_type": payer_type,
            "status": info.get("cargoStatus"),
            "params": f"{int(c.get('amount', 0))}м | {c.get('weight')}кг | {c.get('volume')}м3",
            "arrival": info.get("arrivalPlanDateTime"),
            "payment": payment_status, # НАША НОВАЯ ЛОГИКА
            "route": f"{clean_name(i.get('sender', {}).get('branch'), True)} ➡️ {clean_name(i.get('receiver', {}).get('branch', {}).get('city'), True)}"
        })
    return results

# --- ФУНКЦИИ СОХРАНЕНИЯ ---

def save_report_to_file(report_lines, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in report_lines:
            f.write(line + '\n')


def save_json_report(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ОСНОВНОЙ ПУЛЬТ ---

# Пути к файлам (убедись, что они в начале модуля)

def run_main_parser():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '..', 'data')
    input_file = os.path.join(data_dir, 'test_all_tk.json')

    if not os.path.exists(input_file):
        return print(f"Файл не найден: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_json = json.load(f)

    raw_results = []
    # Сбор данных от всех ТК
    if "Baikal" in raw_json: raw_results.extend(parse_baikal(raw_json["Baikal"]))
    if "Dellin" in raw_json: raw_results.extend(parse_dellin(raw_json["Dellin"]))
    if "Pecom" in raw_json: raw_results.extend(parse_pecom(raw_json["Pecom"]))

    manual_file = os.path.join(data_dir, 'manual_cargo.json')
    manual_data = []
    if os.path.exists(manual_file):
        with open(manual_file, 'r', encoding='utf-8') as f:
            try:
                manual_data = json.load(f)
                # Добавляем памятки в общий список для проверки статусов
                raw_results.extend(manual_data)
            except: pass

    # 1. ЛОГИКА "ПАМЯТИ": Сравниваем с прошлым запуском
    current_ids = {str(r['id']) for r in raw_results}

    if os.path.exists(st.LAST_STATE_FILE):
        with open(st.LAST_STATE_FILE, 'r', encoding='utf-8') as f:
            try: last_active = json.load(f)
            except: last_active = []
    else:
        last_active = []

    # Ищем тех, кто пропал из API (значит, выдали или удалили)
    missing_items = []
    for item in last_active:
        if str(item['id']) not in current_ids:
            item['status'] = "Выдан (автоархив)"
            missing_items.append(item)

    # 2. КЛАССИФИКАЦИЯ ТЕКУЩИХ
    EXCLUDE = ["выдан", "доставлен", "завершен", "архив", "выдача", "получен"]

    active = sorted(
        [r for r in raw_results if not any(k in str(r.get('status', '')).lower() for k in EXCLUDE)],
        key=lambda x: str(x.get('arrival') or "9999")
    )

    # Заказы (включая памятки), которые ПРЯМО СЕЙЧАС имеют статус "Выдан"
    just_finished_api = [r for r in raw_results if any(k in str(r.get('status', '')).lower() for k in EXCLUDE)]


    # 3. АРХИВАЦИЯ (Объединяем явно выданные и пропавшие из эфира)
    to_archive = just_finished_api + missing_items
    update_permanent_archive(to_archive)

    # Сохраняем текущий актив для следующего сравнения
    with open(st.LAST_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(active, f, ensure_ascii=False, indent=4)

    # 4. ПОДГОТОВКА ДАННЫХ ДЛЯ ФРОНТЕНДА
    full_history = []
    if os.path.exists(st.HISTORY_FILE):
        with open(st.HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                full_history = json.load(f)
                # Сортировка с защитой: если даты нет, ставим очень старую
                full_history.sort(
                    key=lambda x: datetime.strptime(x.get('archived_at', '01.01.2020'), '%d.%m.%Y'),
                    reverse=True
                )
            except Exception as e:
                print(f"[Error] Ошибка чтения/сортировки истории: {e}")
                # Если упали — всё равно берем то, что прочитали, или хотя бы новые
                if not full_history:
                    full_history = to_archive
    else:
        full_history = to_archive

    report_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    json_data = {
        "metadata": {
            "created_at": report_time,
            "active_count": len(active),
            "archive_count": len(full_history)
        },
        "active": active,
        "archive": full_history
    }

    # 5. КОНСОЛЬНЫЙ ВЫВОД (возвращаем сводку)
    print(f"\nОТЧЕТ ТРАНСПОРТ | {report_time}")
    print("="*150)
    head = f"{'ТК':<15} | {'№ Накладной':<18} | {'Отправитель':<20} | {'Маршрут':<25} | {'Статус':<30} | {'Прибытие':<10}"
    print(head)
    print("-"*150)
    for r in active:
        line = (f"{r['tk']:<15} | {str(r['id']):<18} | {str(r['sender'])[:19]:<20} | "
                f"{str(r['route'])[:24]:<25} | {str(r['status'])[:29]:<30} | {str(r['arrival'] or 'Н/Д')[:10]:<10}")
        print(line)

    # --- НОВОЕ: ЧИСТИМ ПАМЯТКИ, КОТОРЫЕ УШЛИ В АРХИВ ---
    if manual_data:
        # Оставляем только те памятки, которые НЕ попали в список "на вылет"
        active_ids = {str(a['id']) for a in active}
        remaining_manual = [m for m in manual_data if str(m['id']) in active_ids]

        with open(manual_file, 'w', encoding='utf-8') as f:
            json.dump(remaining_manual, f, ensure_ascii=False, indent=4)
        print(f"[Manual] Очистка завершена. Осталось ручных записей: {len(remaining_manual)}")

    # 6. СОХРАНЕНИЕ ОТЧЕТОВ
    date_str = datetime.now().strftime('%Y-%m-%d')

    # Основной отчет для прода (с датой)
    save_json_report(json_data, os.path.join(data_dir, f"report_{date_str}.json"))

    # Отчет для DEV-сервера (всегда свежий статический файл)
    save_json_report(json_data, os.path.join(data_dir, "test_all_tk_processed.json"))

    cleanup_old_reports(data_dir, days=14)

    print(f"\n[✓] Обработка завершена. Активно: {len(active)}, Добавлено в архив: {len(to_archive)}")




if __name__ == "__main__":
    run_main_parser()
