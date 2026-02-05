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


import json
import os
import re
from datetime import datetime

import settings as st


def update_permanent_archive(new_archive_items):
    """Сохраняет уникальные завершенные заказы в вечный архив"""
    # 1. Читаем существующий архив
    if os.path.exists(st.HISTORY_FILE):
        with open(st.HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                old_history = json.load(f)
            except:
                old_history = []
    else:
        old_history = []

    # 2. Создаем набор ID, которые уже есть в архиве (чтобы не дублировать)
    existing_ids = {str(item['id']) for item in old_history}

    # 3. Добавляем только те, которых еще нет
    added_count = 0
    for item in new_archive_items:
        if str(item['id']) not in existing_ids:
            # Добавляем дату перемещения в архив для порядка
            item['archived_at'] = datetime.now().strftime('%d.%m.%Y')
            old_history.append(item)
            existing_ids.add(str(item['id']))
            added_count += 1

    # 4. Сохраняем обновленный архив
    if added_count > 0:
        with open(st.HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(old_history, f, ensure_ascii=False, indent=4)
        print(f"[Archive] Добавлено новых записей в историю: {added_count}")

def clean_name(text, is_city=False):
    if not text or not isinstance(text, str): return "???"
    cleaned = re.sub(r'\(.*?\)', '', text).lower()

    if is_city:
        city_trash = ["г. ", "город ", "пгт. ", "поселок ", "область", "обл.", " край", " р-н", " мо", " г "]
        for trash in city_trash: cleaned = cleaned.replace(trash, "")

        # Сокращаем терминалы и стороны света
        replacements = {
            "восток": "ВСТ", "запад": "ЗПД", "север": "СЕВ", "юг": "ЮГ",
            "терминал": "ТЕРМ", "склад": "СКЛ", "центральный": "ЦЕНТР"
        }
        for long, short in replacements.items():
            cleaned = cleaned.replace(long, short)

        cleaned = cleaned.strip()
        for full, short in st.CITY_MAP.items():
            if full in cleaned: cleaned = cleaned.replace(full, short)
    else:
        replacements = {
            "общество с ограниченной ответственностью": "ООО",
            "индивидуальный предприниматель": "ИП",
            "акционерное общество": "АО"
        }
        for long, short in replacements.items(): cleaned = cleaned.replace(long, short)

    cleaned = cleaned.replace('"', '').replace('«', '').replace('»', '')
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
        first_item = cargo_list[0] if cargo_list else {}

        # Считаем параметры
        places = sum(int(item.get("cargo", {}).get("places") or 0) for item in cargo_list)
        weight = sum(float(item.get("cargo", {}).get("weight") or 0) for item in cargo_list)
        volume = sum(float(item.get("cargo", {}).get("volume") or 0) for item in cargo_list)

        results.append({
            "tk": "Байкал Сервис",
            "id": order.get("number") or "Н/Д",
            "sender": clean_name(first_item.get("consignor", {}).get("name")),
            "status": order.get("orderstatus", "Н/Д"),
            "params": f"{places}м/ {weight}кг/ {volume}м3",
            "arrival": first_item.get('dateArrivalPlane') or order.get('dateArrivalPlane'),
            "payment": order.get("paidStatus") or "Н/Д",
            "route": f"{clean_name(first_item.get('departure', {}).get('name'), True)} -> {clean_name(first_item.get('destination', {}).get('name'), True)}"
        })
    return results

def parse_dellin(data):
    results = []
    for o in data.get("orders", []):
        f = o.get("freight", {})
        results.append({
            "tk": "Деловые Линии", "id": o.get("orderId"),
            "sender": clean_name(o.get("sender", {}).get("name")),
            "status": f"{o.get('stateName')} ({o.get('progressPercent')}%)",
            "params": f"{f.get('places')}м/ {f.get('weight')}кг/ {f.get('volume')}м3",
            "arrival": o.get("orderDates", {}).get("arrivalToOspReceiver"),
            "payment": "Оплачено" if o.get("isPaid") else "Не оплачено",
            "route": f"{clean_name(o.get('derival', {}).get('city'), True)} -> {clean_name(o.get('arrival', {}).get('city'), True)}"
        })
    return results

def parse_pecom(data):
    results = []
    for i in data.get("cargos", []):
        c = i.get("cargo", {})
        debt = i.get("services", {}).get("debt", 0)
        results.append({
            "tk": "ПЭК", "id": c.get("cargoBarCode"),
            "sender": clean_name(i.get("sender", {}).get("sender")),
            "status": i.get("info", {}).get("cargoStatus"),
            "params": f"{c.get('amount')}м/ {c.get('weight')}кг/ {c.get('volume')}m3",
            "arrival": i.get("info", {}).get("arrivalPlanDateTime"),
            "payment": "Оплачено" if debt <= 0 else f"Долг: {debt}",
            "route": f"{clean_name(i.get('sender', {}).get('branchInfo', {}).get('city'), True)} -> {clean_name(i.get('receiver', {}).get('branch', {}).get('city'), True)}"
        })
    return results

# --- ФУНКЦИИ СОХРАНЕНИЯ ---

def save_report_to_file(report_lines, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in report_lines: f.write(line + '\n')

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
        [r for r in raw_results if not any(k in str(r['status']).lower() for k in EXCLUDE)],
        key=lambda x: str(x['arrival'] or "9999")
    )

    # Заказы, которые ПРЯМО СЕЙЧАС в API имеют статус "Выдан"
    just_finished_api = [r for r in raw_results if any(k in str(r['status']).lower() for k in EXCLUDE)]

    # 3. АРХИВАЦИЯ (Объединяем явно выданные и пропавшие из эфира)
    to_archive = just_finished_api + missing_items
    update_permanent_archive(to_archive)

    # Сохраняем текущий актив для следующего сравнения
    with open(st.LAST_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(active, f, ensure_ascii=False, indent=4)

    # 4. ПОДГОТОВКА ДАННЫХ ДЛЯ ФРОНТЕНДА
    if os.path.exists(st.HISTORY_FILE):
        with open(st.HISTORY_FILE, 'r', encoding='utf-8') as f:
            try: full_history = json.load(f)
            except: full_history = to_archive
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

    # 6. СОХРАНЕНИЕ ОТЧЕТОВ
    date_str = datetime.now().strftime('%Y-%m-%d')
    save_json_report(json_data, os.path.join(data_dir, f"report_{date_str}.json"))
    save_json_report(json_data, os.path.join(data_dir, "test_all_tk_processed.json"))

    print(f"\n[✓] Обработка завершена. Активно: {len(active)}, Добавлено в архив: {len(to_archive)}")




if __name__ == "__main__":
    run_main_parser()
