import json
import os
import re
from datetime import datetime

RED = ""
GREEN = ""
RESET = ""
BOLD = ""

def clean_name(text, is_city=False):
    if not text or not isinstance(text, str): return "???"
    cleaned = re.sub(r'\(.*?\)', '', text).lower()
    if is_city:
        city_trash = ["г. ", "город ", "пгт. ", "поселок ", "область", "обл.", " край", " р-н", " мо", " г "]
        for trash in city_trash: cleaned = cleaned.replace(trash, "")
    else:
        replacements = {"общество с ограниченной ответственностью": "ООО", "индивидуальный предприниматель": "ИП", "акционерное общество": "АО", "публичное акционерное общество": "ПАО", "товарищество с ограниченной ответственностью": "ТОО"}
        for long, short in replacements.items(): cleaned = cleaned.replace(long, short)
    cleaned = cleaned.replace('"', '').replace('«', '').replace('»', '')
    return " ".join(cleaned.split()).strip().upper()

# --- ОБРАБОТЧИКИ ТК (без изменений) ---

def parse_baikal(data):
    cargo_list = data.get("cargoList", [])

    # ИСПРАВЛЕНИЕ: Берем ПЕРВЫЙ элемент списка, если он существует, иначе пустой словарь
    first_item = cargo_list[0] if cargo_list else {}

    # Теперь first_item гарантированно является словарем, можно использовать .get()
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
        results.append({"tk": "Деловые Линии", "id": o.get("orderId"), "sender": clean_name(o.get("sender", {}).get("name")), "status": f"{o.get('stateName')} ({o.get('progressPercent')}%)", "params": f"{f.get('places')}м/ {f.get('weight')}кг/ {f.get('volume')}м3", "arrival": o.get("orderDates", {}).get("arrivalToOspReceiver"), "payment": "Оплачено" if o.get("isPaid") else "Не оплачено", "route": f"{clean_name(o.get('derival', {}).get('city'), True)} -> {clean_name(o.get('arrival', {}).get('city'), True)}"})
    return results

def parse_pecom(data):
    results = []
    for i in data.get("cargos", []):
        c = i.get("cargo", {})
        debt = i.get("services", {}).get("debt", 0)
        results.append({"tk": "ПЭК", "id": c.get("cargoBarCode"), "sender": clean_name(i.get("sender", {}).get("sender")), "status": i.get("info", {}).get("cargoStatus"), "params": f"{c.get('amount')}м/ {c.get('weight')}кг/ {c.get('volume')}m3", "arrival": i.get("info", {}).get("arrivalPlanDateTime"), "payment": "Оплачено" if debt <= 0 else f"Долг: {debt}", "route": f"{clean_name(i.get('sender', {}).get('branchInfo', {}).get('city'), True)} -> {clean_name(i.get('receiver', {}).get('branch', {}).get('city'), True)}"})
    return results

# --- ФУНКЦИЯ СОХРАНЕНИЯ В ФАЙЛ ---

def save_report_to_file(report_lines, file_path):
    """Сохраняет список строк отчета в текстовый файл."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in report_lines:
                f.write(line + '\n')
        print(f"\n[✓] Отчет успешно сохранен в файл: {file_path}")
    except IOError as e:
        print(f"\n[!] Ошибка при сохранении файла отчета: {e}")


# --- ОСНОВНОЙ ПУЛЬТ ---

def run_main_parser():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, '..', 'data', 'test_all_tk.json')
    if not os.path.exists(file_path): return print("Файл не найден!")

    with open(file_path, 'r', encoding='utf-8') as f: raw_json = json.load(f)
    raw_results = []
    if "Baikal" in raw_json: raw_results.append(parse_baikal(raw_json["Baikal"]))
    if "Dellin" in raw_json: raw_results.extend(parse_dellin(raw_json["Dellin"]))
    if "Pecom" in raw_json: raw_results.extend(parse_pecom(raw_json["Pecom"]))

    EXCLUDE = ["выдан", "доставлен", "завершен", "архив", "выдача"]
    active = sorted([r for r in raw_results if not any(k in str(r['status']).lower() for k in EXCLUDE)],
                    key=lambda x: str(x['arrival'] or "9999"))
    hidden = [r for r in raw_results if any(k in str(r['status']).lower() for k in EXCLUDE)]

    # Собираем все строки отчета сначала в список, чтобы потом сохранить в файл
    report_lines = []
    report_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

    report_lines.append(f"\nОТЧЕТ ТРАНСПОРТ | {report_time}")
    report_lines.append("="*185)
    head = f"{'ТК':<15} | {'№ Накладной':<18} | {'Отправитель':<25} | {'Маршрут':<30} | {'Статус':<35} | {'Прибытие':<10} | {'Оплата':<15}"
    report_lines.append(head)
    report_lines.append("-"*185)

    for r in active:
        line = (f"{r['tk']:<15} | {str(r['id']):<18} | {str(r['sender'])[:24]:<25} | "
                f"{str(r['route'])[:29]:<30} | {str(r['status'])[:34]:<35} | "
                f"{str(r['arrival'] or 'Н/Д')[:10]:<10} | {r['payment']:<15}")
        report_lines.append(line)

    if hidden:
        report_lines.append(f"\n[✓] АРХИВ ВЫДАННЫХ:")
        for h in hidden:
            report_lines.append(f"ВЫДАНО | {h['tk']:<15} | {str(h['id']):<18} | {str(h['sender'])[:24]:<25} | {h['status']}")

    # Выводим в консоль (как раньше)
    for line in report_lines:
        print(line)

    # Сохраняем в файл log_report_YYYY-MM-DD.txt в папке data
    file_name = f"log_report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    save_path = os.path.join(base_dir, '..', 'data', file_name)
    save_report_to_file(report_lines, save_path)


if __name__ == "__main__":
    run_main_parser()
