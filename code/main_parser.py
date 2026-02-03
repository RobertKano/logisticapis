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

# --- КОНФИГУРАЦИЯ И СЛОВАРИ ---
CITY_MAP = {
    "астрахань": "АСТРА",
    "санкт-петербург": "СПБ",
    "новосибирск": "НСК",
    "екатеринбург": "ЕКБ",
    "нижний новгород": "Н.НОВ",
    "краснодар": "КРД",
    "ростов-на-дону": "РНД",
    "домодедово": "ДМД",
    "одинцово": "ОДИН",
    "пермь": "ПРМ",
    "казань": "КЗН",
    "челябинск": "ЧЛБ",
    "красноярск": "КРЯ",
    "москва": "МСК",
    "владивосток": "ВЛД"
}

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
        for full, short in CITY_MAP.items():
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
    cargo_list = data.get("cargoList", [])
    first_item = cargo_list[0] if cargo_list else {}
    arrival_raw = first_item.get('dateArrivalPlane') or data.get('dateArrivalPlane')

    places = sum(int(item.get("cargo", {}).get("places") or 0) for item in cargo_list)
    weight = sum(float(item.get("cargo", {}).get("weight") or 0) for item in cargo_list)
    volume = sum(float(item.get("cargo", {}).get("volume") or 0) for item in cargo_list)

    c_from = clean_name(first_item.get('departure', {}).get('name'), is_city=True)
    c_to = clean_name(first_item.get('destination', {}).get('name'), is_city=True)

    return {
        "tk": "Байкал Сервис", "id": data.get("number") or "Н/Д",
        "sender": clean_name(first_item.get("consignor", {}).get("name")),
        "status": data.get("orderstatus", "Н/Д"),
        "params": f"{places}м/ {weight}кг/ {volume}м3", "arrival": arrival_raw,
        "payment": data.get("paidStatus") or "Н/Д",
        "route": f"{c_from} -> {c_to}"
    }

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

def run_main_parser():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '..', 'data')
    input_file = os.path.join(data_dir, 'test_all_tk.json')

    if not os.path.exists(input_file): return print(f"Файл не найден: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f: raw_json = json.load(f)

    raw_results = []
    if "Baikal" in raw_json: raw_results.append(parse_baikal(raw_json["Baikal"]))
    if "Dellin" in raw_json: raw_results.extend(parse_dellin(raw_json["Dellin"]))
    if "Pecom" in raw_json: raw_results.extend(parse_pecom(raw_json["Pecom"]))

    EXCLUDE = ["выдан", "доставлен", "завершен", "архив", "выдача"]
    active = sorted([r for r in raw_results if not any(k in str(r['status']).lower() for k in EXCLUDE)],
                    key=lambda x: str(x['arrival'] or "9999"))
    hidden = [r for r in raw_results if any(k in str(r['status']).lower() for k in EXCLUDE)]

    report_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

    # СБОРКА ТЕКСТОВОГО ОТЧЕТА
    report_lines = [f"\nОТЧЕТ ТРАНСПОРТ | {report_time}", "="*165]
    head = f"{'ТК':<15} | {'№ Накладной':<18} | {'Отправитель':<20} | {'Маршрут':<25} | {'Груз':<22} | {'Статус':<25} | {'Прибытие':<10} | {'Оплата':<12}"
    report_lines.append(head)
    report_lines.append("-"*165)

    for r in active:
        line = (f"{r['tk']:<15} | {str(r['id']):<18} | {str(r['sender'])[:19]:<20} | "
                f"{str(r['route'])[:24]:<25} | {str(r['params']):<22} | "
                f"{str(r['status'])[:24]:<25} | {str(r['arrival'] or 'Н/Д')[:10]:<10} | {str(r['payment'])[:12]:<12}")
        report_lines.append(line)

    # СБОРКА JSON
    json_data = {
        "metadata": {"created_at": report_time, "active_count": len(active)},
        "active": active,
        "archive": hidden
    }

    # ВЫВОД И СОХРАНЕНИЕ
    for line in report_lines: print(line)

    date_str = datetime.now().strftime('%Y-%m-%d')
    save_report_to_file(report_lines, os.path.join(data_dir, f"log_report_{date_str}.txt"))
    save_json_report(json_data, os.path.join(data_dir, f"report_{date_str}.json"))
    print(f"\n[✓] Отчеты (TXT + JSON) сохранены в папку data")

if __name__ == "__main__":
    run_main_parser()
