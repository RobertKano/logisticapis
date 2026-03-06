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
from datetime import timedelta
from bs4 import BeautifulSoup
from database import CargoDB

import settings as st


class MemoryManager:
    def __init__(self, db, last_state_file):
        self.db = db
        self.file = last_state_file

    def get_last_active(self):
        if os.path.exists(self.file):
            with open(self.file, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []

    def restore_ghosts(self, current_results):
        """Возвращает список грузов, которые пропали из API, но еще живы (48ч)"""
        current_ids = {str(r['id']) for r in current_results}
        last_active = self.get_last_active()

        ghosts = []
        to_archive_missing = []

        for item in last_active:
            cargo_id = str(item['id'])
            if cargo_id in current_ids:
                continue

            # 1. Если статус уже финальный - не ждем, сразу в архив
            status_upper = str(item.get('status', '')).upper()
            is_finished = any(word in status_upper for word in ["ВЫДАН", "ДОСТАВЛЕН", "АРХИВ", "ПОЛУЧЕН"])

            if is_finished:
                item['status'] = "ВЫДАН (АВТОАРХИВ)"
                to_archive_missing.append(item)
                continue

            # 2. Проверка 48 часов через БД
            try:
                with self.db.get_connection() as conn:
                    res = conn.execute("SELECT updated_at FROM cargo WHERE id = ?", (cargo_id,)).fetchone()
                    if res and res[0]:
                        last_seen = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
                        if (datetime.now() - last_seen).total_seconds() < 48 * 3600:
                            # Помечаем "призрака" восклицательным знаком
                            if "!" not in str(item.get('status')):
                                item['status'] = f"! {item.get('status')} (НЕ В API)"
                            ghosts.append(item)
                            continue
            except Exception as e:
                print(f"[Memory] Ошибка времени для {cargo_id}: {e}")

            # 3. Иначе - в архив (пропал давно или нет в БД)
            item['status'] = "ВЫДАН (АВТОАРХИВ)"
            to_archive_missing.append(item)

        return ghosts, to_archive_missing


class CargoClassifier:
    def __init__(self, db, exclude_list):
        self.db = db
        self.exclude = [k.lower() for k in exclude_list]

    def _get_stuck_bsd_ids(self):
        """Получаем ID БСД, которые база пометила архивными (28ч)"""
        try:
            with self.db.get_connection() as conn:
                res = conn.execute("""
                    SELECT id FROM cargo WHERE tk = 'БСД'
                    AND (status LIKE '%ПРИБЫЛ%' OR status LIKE '%ДОСТАВКА%')
                    AND archived_at IS NOT NULL
                """).fetchall()
                return {str(row[0]) for row in res}
        except: return set()

    def classify(self, results_pool, missing_from_api):
        stuck_ids = self._get_stuck_bsd_ids()
        active, archive_api = [], []
        today_str = datetime.now().strftime('%Y-%m-%d')

        for r in results_pool:
            cargo_id = str(r.get('id'))
            status_low = str(r.get('status', '')).lower()

            is_finished = any(k in status_low for k in self.exclude)
            is_stuck = cargo_id in stuck_ids

            if is_finished or is_stuck:
                if is_stuck: r['status'] = "ВЫДАН (АВТОАРХИВ БСД)"
                if r.get('tk') == "БСД" and r.get('arrival') == "САМОВЫВОЗ":
                    r['arrival'] = today_str
                archive_api.append(r)
            else:
                active.append(r)

        full_archive = archive_api + missing_from_api
        active.sort(key=lambda x: str(x.get('arrival') or "9999"))
        return active, full_archive



def cleanup_old_reports(keep_count=7):
    """Оставляет только N последних файлов report_*.json"""
    import glob
    # Используем путь из настроек
    files = sorted(glob.glob(os.path.join(st.DATA_DIR, "report_*.json")), reverse=True)
    for old_file in files[keep_count:]:
        try:
            os.remove(old_file)
            print(f"[Cleanup] Удален старый отчет: {os.path.basename(old_file)}")
        except:
            pass

def update_permanent_archive(new_archive_items):
    """Сохраняет завершенные заказы в JSON и в будущую БД"""
    if not new_archive_items:
        return

    # Читаем существующий JSON архив
    old_history = []
    if os.path.exists(st.HISTORY_FILE):
        try:
            with open(st.HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    old_history = json.loads(content)
        except:
            old_history = []

    existing_ids = {str(item.get('id')) for item in old_history if item.get('id')}
    added_count = 0

    for item in new_archive_items:
        cargo_id = str(item.get('id', ''))
        if not cargo_id or cargo_id in existing_ids:
            continue

        item['archived_at'] = datetime.now().strftime('%d.%m.%Y')
        old_history.append(item)
        existing_ids.add(cargo_id)
        added_count += 1

    if added_count > 0:
        with open(st.HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(old_history, f, ensure_ascii=False, indent=4)
        print(f"[Archive] В JSON добавлено: {added_count}. Всего: {len(old_history)}")

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
    if not data or not isinstance(data, list):
        return []

    results = []
    for order in data:
        if order.get("status") == "empty":
            continue

        cargo_list = order.get("cargoList", [])
        if not cargo_list: continue

        first_item = cargo_list[0]
        consignor = first_item.get("consignor", {})
        consignee = first_item.get("consignee", {})

        # Логика определения плательщика (оставляем твою)
        services = first_item.get("services", [])
        payer_data = services[0].get("payer", {}) if services else {}
        payer_inn = payer_data.get("inn")

        if payer_inn == consignee.get("inn"):
            payer_type = "recipient"
        elif payer_inn == consignor.get("inn"):
            payer_type = "sender"
        else:
            payer_type = "third_party"

        # Считаем параметры (оставляем твой sum)
        places = sum(int(item.get("cargo", {}).get("places") or 0) for item in cargo_list)
        weight = sum(float(item.get("cargo", {}).get("weight") or 0) for item in cargo_list)
        volume = sum(float(item.get("cargo", {}).get("volume") or 0) for item in cargo_list)

        # Расчет долга и общей стоимости (total_sum)
        total = order.get("total") or first_item.get("total", {})
        total_sum = float(total.get("sum") or 0) # ВОТ ТВОЯ СУММА ДЛЯ АНАЛИТИКИ
        total_paid = float(total.get("paid") or 0)
        debt = round(total_sum - total_paid, 2)

        if debt > 0:
            payment_status = f"К ОПЛАТЕ: {debt}"
        else:
            payment_status = order.get("paidStatus") or "ОПЛАЧЕНО"

        # Чистим дату (берем первые 10 символов YYYY-MM-DD)
        arrival_raw = first_item.get('dateArrivalPlane') or order.get('dateArrivalPlane') or "САМОВЫВОЗ"
        arrival = str(arrival_raw)[:10]

        results.append({
            "tk": "БАЙКАЛ СЕРВИС",
            "id": order.get("tracking") or "Н/Д",
            "sender": clean_name(consignor.get("name")),
            "recipient": clean_name(consignee.get("name")),
            "payer_type": payer_type,
            "status": str(order.get("orderstatus", "Н/Д")).upper(), # В UPPER
            "params": f"{places}М | {weight}КГ | {volume}М3", # В UPPER
            "arrival": arrival, # YYYY-MM-DD
            "payment": payment_status.upper(), # В UPPER
            "total_price": total_sum, # ЧИСТОЕ ЧИСЛО ДЛЯ АНАЛИТИКИ
            "is_manual": False,
            "route": f"{clean_name(first_item.get('departure', {}).get('name'), True)} -> {clean_name(first_item.get('destination', {}).get('name'), True)}"
        })
    return results


def parse_dellin(data):
    results = []
    # Работаем через список orders, как в твоем исходнике
    for o in data.get("orders", []):
        # 1. Извлекаем основной документ (накладную)
        docs = o.get("documents", [])
        main_doc = docs[0] if docs else {}

        f = o.get("freight", {})
        sender_data = o.get("sender", {})
        receiver_data = o.get("receiver", {})
        payer_data = o.get("payer", {})

        # --- ТВОЯ ЛОГИКА ОПРЕДЕЛЕНИЯ СТАТУСА ОПЛАТЫ ---
        debt = float(main_doc.get("debtSum") or 0)
        is_paid_root = o.get("isPaid", False)

        # ВЫТАСКИВАЕМ СУММУ ДЛЯ АНАЛИТИКИ (totalSum)
        # Берем из документа или из корня заказа
        total_sum = float(main_doc.get("totalSum") or o.get("totalSum", 0))

        if debt > 0:
            payment_status = f"К ОПЛАТЕ: {debt}"
        elif is_paid_root:
            payment_status = "ОПЛАЧЕНО"
        else:
            payment_status = f"К ОПЛАТЕ: {total_sum}"

        # --- ТВОЯ ЛОГИКА PAYER_TYPE ---
        p_inn = payer_data.get("inn")
        r_inn = receiver_data.get("inn")

        if p_inn and r_inn and p_inn == r_inn:
            payer_type = "recipient"
        elif p_inn and p_inn == sender_data.get("inn"):
            payer_type = "sender"
        else:
            payer_type = "third_party"

        # 2. ЧИСТИМ ДАТУ (YYYY-MM-DD)
        arrival_raw = o.get("orderDates", {}).get("arrivalToOspReceiver") or "САМОВЫВОЗ"
        arrival = str(arrival_raw)[:10]

        results.append({
            "tk": "ДЕЛОВЫЕ ЛИНИИ",
            "id": str(o.get("orderId", "Н/Д")),
            "sender": clean_name(sender_data.get("name")),
            "recipient": clean_name(receiver_data.get("name")),
            "payer_type": payer_type,
            # Добавляем процент прогресса в UPPER статус
            "status": f"{o.get('stateName')} ({o.get('progressPercent')}%)".upper(),
            "params": f"{f.get('places', 1)}М | {f.get('weight', 0)}КГ | {f.get('volume', 0)}М3",
            "arrival": arrival,
            "payment": payment_status.upper(),
            "total_price": round(total_sum, 2), # ЧИСТОЕ ЧИСЛО ДЛЯ АНАЛИЗА
            "is_manual": False,                # ОБЯЗАТЕЛЬНОЕ ПОЛЕ
            "route": f"{clean_name(o.get('derival', {}).get('terminalCity') or o.get('derival', {}).get('city'), True)} -> {clean_name(o.get('arrival', {}).get('terminalCity') or o.get('arrival', {}).get('city'), True)}"
        })
    return results


def parse_pecom(data):
    results = []
    # Работаем через cargos, как в твоем исходнике
    for i in data.get("cargos", []):
        c = i.get("cargo", {})
        info = i.get("info", {})
        services = i.get("services", {})
        service_items = services.get("items", [])

        # 1. РАСЧЕТ СУММЫ (total_price)
        # Суммируем все услуги из service_items для аналитики
        total_sum = sum(float(s.get("sum", 0)) for s in service_items)
        total_debt = float(services.get("debt", 0))

        # 2. ТВОЯ ЛОГИКА СТАТУСА ОПЛАТЫ
        has_unpaid_service = any(s.get("payToReceive") is True for s in service_items)

        if total_debt <= 0 and not has_unpaid_service:
            payment_status = "ОПЛАЧЕНО"
        else:
            payment_status = f"К ОПЛАТЕ: {total_debt}"

        # 3. ТВОЯ ЛОГИКА PAYER_TYPE
        p_types = [s.get("payerType") for s in service_items]
        if all(pt == 2 for pt in p_types):
            payer_type = "recipient"
        elif all(pt == 1 for pt in p_types):
            payer_type = "sender"
        else:
            payer_type = "third_party"

        # 4. ЧИСТИМ ДАТУ (YYYY-MM-DD)
        arrival_raw = info.get("arrivalPlanDateTime") or "САМОВЫВОЗ"
        arrival = str(arrival_raw)[:10]

        results.append({
            "tk": "ПЭК",
            "id": str(c.get("cargoBarCode", "Н/Д")),
            "sender": clean_name(i.get("sender", {}).get("sender")),
            "recipient": clean_name(i.get("receiver", {}).get("receiver")),
            "payer_type": payer_type,
            "status": str(info.get("cargoStatus", "Н/Д")).upper(),
            "params": f"{int(c.get('amount', 0))}М | {c.get('weight', 0)}КГ | {c.get('volume', 0)}М3",
            "arrival": arrival,
            "payment": payment_status.upper(),
            "total_price": round(total_sum, 2), # Чистое число для анализа
            "is_manual": False,                # Обязательное поле
            "route": f"{clean_name(i.get('sender', {}).get('branch'), True)} -> {clean_name(i.get('receiver', {}).get('branch', {}).get('city'), True)}"
        })
    return results


def parse_viteka(html_list):
    """Парсинг БСД с глубокой очисткой получателя и статусов"""
    results = []
    if not html_list: return results

    for html in html_list:
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.select('#orders-table-body tr')

        for row in rows:
            tds = row.find_all('td')
            if len(tds) < 12: continue

            # 1. Поиск номера накладной через регулярное выражение
            # Шаблон: 2 заглавные буквы, 2 цифры, дефис, цифры (например, СП00-1234)
            order_text = tds[0].get_text(strip=True).upper()
            match = re.search(r'([А-ЯA-Z]{2}\d{2}-\d+)', order_text)

            if match:
                order_id = match.group(1) # Забираем найденный номер целиком
            else:
                # Если в ячейке только цифры (заявка) - пропускаем
                continue

            # 2. ЧИСТКА ПОЛУЧАТЕЛЯ (Убираем "ИЗМЕНИТЬ ПОЛУЧАТЕЛЯ...")
            # Берем только текст ДО кнопок/форм внутри ячейки
            raw_recipient = tds[7].get_text(" ", strip=True)
            # Отсекаем всё, что начинается со слова "ИЗМЕНИТЬ" или "ПОМЕНЯТЬ"
            clean_recipient_raw = re.split(r'ИЗМЕНИТЬ|ПОМЕНЯТЬ', raw_recipient)[0].strip()
            recipient = clean_name(clean_recipient_raw)

            # 3. ЧИСТКА СТАТУСА (Делаем максимально просто для main.js)
            status_raw = tds[1].get_text(" ", strip=True).upper()

            if "ВЫДАН" in status_raw:
                display_status = "ВЫДАН"
            elif "ПРИБЫЛ" in status_raw or "СКЛАД" in status_raw:
                display_status = "ПРИБЫЛ В ТК"
            else:
                # Для всех остальных состояний (пути, отправка, ожидается)
                # Даем просто "В ПУТИ", чтобы main.js не рисовал (+4Д)
                display_status = "В ПУТИ"

            # 4. ДАТА ПРИБЫТИЯ (Чистая дата для БД)
            arrival_match = re.search(r'(\d{2})\.(\d{2})\.(\d{2,4})', status_raw)
            if arrival_match:
                d, m, y = arrival_match.groups()
                full_year = f"20{y}" if len(y) == 2 else y
                arrival = f"{full_year}-{m}-{d}"
            else:
                arrival = (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d')

            # 5. ПАРАМЕТРЫ
            def get_val(label):
                found = tds[3].find('span', string=re.compile(label))
                return found.find_next('span').get_text(strip=True) if found else "0"

            payment_raw = tds[8].get_text(strip=True) # Берем чистый текст из 8-й колонки

            # Сначала проверяем на негативный статус, чтобы он не попал в "Оплачено"
            if "Не оплачена" in payment_raw:
                payment_display = "К оплате"
            elif "Оплачена" in payment_raw:
                payment_display = "Оплачено"
            else:
                # На случай, если БСД пришлет пустую строку или "В обработке"
                payment_display = "Н/Д"

            results.append({
                "tk": "БСД",
                "id": order_id,
                "sender": clean_name(tds[6].get_text(strip=True)),
                "recipient": recipient, # ТЕПЕРЬ ТУТ ТОЛЬКО "ЮЖНЫЙ ФОРПОСТ"
                "route": f"{clean_name(tds[4].get_text(strip=True), True)} -> {clean_name(tds[5].get_text(strip=True), True)}",
                "status": display_status,
                "params": f"{get_val('мест')}М | {get_val('Вес').replace('кг','')}КГ | {get_val('Объем').replace('м3','')}М3",
                "arrival": arrival,
                "payment": payment_display,
                "total_price": float(re.sub(r'[^\d.]', '', tds[11].get_text(strip=True).replace(',','.')) or 0),
                "payer_type": "recipient",
                "is_manual": False
            })
    return results


def parse_magic(items_list):
    """Парсинг и глубокая очистка данных МЭДЖИК под твой main.js"""
    results = []
    if not items_list: return results

    for item in items_list:
        # 1. ПЕРЕИМЕНОВАНИЕ ТК
        tk_name = "МЭДЖИК"

        # 2. ЧИСТКА РОУТОВ (Сплитуем "Москва - Астрахань" через дефис)
        route_raw = str(item.get('route', 'Н/Д'))
        if " - " in route_raw:
            parts = route_raw.split(" - ")
            # Чистим города через твой clean_name с флагом True
            from_city = clean_name(parts[0].strip(), True)
            to_city = clean_name(parts[1].strip(), True)
            route = f"{from_city} -> {to_city}"
        else:
            route = clean_name(route_raw, True)

        # 3. ЛОГИКА СТАТУСОВ (Синхронизация с твоим main.js)
        status_raw = str(item.get('status', '')).upper()

        # Если в Excel есть "ДОСТАВКЕ", даем статус со словом "ДОСТАВКА"
        # Твой JS (rawStatus.includes('оставк')) поймает это и покажет "Доставка ТК ➡️ СКЛАД"
        if "ДОСТАВКЕ" in status_raw or "ЭКСПЕДИРОВАНИЕ" in status_raw:
            display_status = "ДОСТАВКА ДО СКЛАДА"
        elif "ПРИБЫЛ" in status_raw:
            display_status = "ПРИБЫЛ В ГОРОД НАЗНАЧЕНИЯ"
        else:
            display_status = status_raw

        # 4. ДАТА ДЛЯ БД (Всегда YYYY-MM-DD)
        arrival_raw = item.get('arrival', '')
        try:
            dt = datetime.strptime(arrival_raw, '%d.%m.%Y')
            arrival_db = dt.strftime('%Y-%m-%d')
        except:
            arrival_db = datetime.now().strftime('%Y-%m-%d')

        results.append({
            "tk": tk_name,
            "id": item.get('id'),
            "sender": clean_name(item.get('sender', 'Н/Д')),
            "recipient": clean_name(item.get('recipient', 'ЮЖНЫЙ ФОРПОСТ')),
            "route": route,
            "status": display_status,
            "params": item.get('params'),
            "arrival": arrival_db,
            "payment": item.get('payment'),
            "total_price": float(item.get('total_price', 0)),
            "payer_type": "recipient" if "ЮЖНЫЙ ФОРПОСТ" in str(item.get('Плательщик', '')).upper() else "sender",
            "is_manual": False
        })
    return results

# --- ФУНКЦИИ СОХРАНЕНИЯ ---

def save_report_to_file(report_lines, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in report_lines:
            f.write(line + '\n')


def save_json_report(data, file_path):
    print(f"[*] Пытаюсь сохранить: {file_path}")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def run_main_parser():
    db = CargoDB()
    memory = MemoryManager(db, st.LAST_STATE_FILE)
    classifier = CargoClassifier(db, ["выдан", "доставлен", "завершен", "архив", "выдача", "получен"])

    if not os.path.exists(st.RAW_DATA_FILE):
        return print(f"Ошибка: Файл не найден: {st.RAW_DATA_FILE}")

    with open(st.RAW_DATA_FILE, 'r', encoding='utf-8') as f:
        try: raw_json = json.load(f)
        except Exception as e: return print(f"Ошибка чтения JSON: {e}")

    # 1. Сбор данных
    raw_results = []
    if "Baikal" in raw_json: raw_results.extend(parse_baikal(raw_json["Baikal"]))
    if "Dellin" in raw_json: raw_results.extend(parse_dellin(raw_json["Dellin"]))
    if "Pecom" in raw_json: raw_results.extend(parse_pecom(raw_json["Pecom"]))
    if "BSD" in raw_json: raw_results.extend(parse_viteka(raw_json["BSD"]))
    if "Magic" in raw_json: raw_results.extend(parse_magic(raw_json["Magic"]))

    # 2. Подготовка базы (28ч для БСД)
    try: db.archive_stuck_bsd()
    except Exception as e: print(f"[Parser] Ошибка авто-архивации БСД: {e}")

    # 3. Обработка "памяти" и Классификация
    ghosts, missing_from_api = memory.restore_ghosts(raw_results)
    raw_results.extend(ghosts)

    active, to_archive = classifier.classify(raw_results, missing_from_api)

    # 4. Сохранение в БД
    for item in to_archive: db.upsert_cargo(item, is_archived=1)
    for item in active: db.upsert_cargo(item, is_archived=0)

    # 5. Обновление архивов и стейта
    update_permanent_archive(to_archive)
    with open(st.LAST_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(active, f, ensure_ascii=False, indent=4)

    # 6. Формирование истории и финальных отчетов
    full_history = []
    if os.path.exists(st.HISTORY_FILE):
        with open(st.HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                full_history = json.load(f)
                full_history.sort(
                    key=lambda x: datetime.strptime(x.get('archived_at', '01.01.2020'), '%d.%m.%Y'),
                    reverse=True
                )
            except Exception as e:
                print(f"[Error] Ошибка сортировки истории: {e}")
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

    date_str = datetime.now().strftime('%Y-%m-%d')
    daily_report_path = os.path.join(st.DATA_DIR, f"report_{date_str}.json")
    save_json_report(json_data, daily_report_path)
    save_json_report(json_data, st.CURRENT_STATE_FILE)

    cleanup_old_reports(7)
    print(f"\n[✓] Обработка завершена. Активно: {len(active)}, В архив: {len(to_archive)}")


if __name__ == "__main__":
    run_main_parser()
