from pathlib import Path
import json
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor # Ускоритель

from api_classes import (
    BK_SECRET_KEY,
    DL_LOGIN,
    DL_PASS,
    DL_SECRET_KEY,
    PC_LOGIN,
    PC_SECRET_KEY,
    VT_LOGIN,
    VT_PASS,
    BaikalApiV2,
    DellinApiV1,
    PecomApiV1,
    VitekaApiV1
)

# Инициализация объектов
p = PecomApiV1(PC_SECRET_KEY, PC_LOGIN)
d = DellinApiV1(DL_SECRET_KEY, DL_LOGIN, DL_PASS)
b = BaikalApiV2(BK_SECRET_KEY)
vt = VitekaApiV1(VT_LOGIN, VT_PASS)

def fetch_baikal_parallel():
    """Специальная функция для Байкала: сначала список, потом параллельно детали"""
    s_bk = time.time()
    list_of_cargo_codes = b.collect_cargocodes()
    results = []

    if list_of_cargo_codes:
        # Запускаем детализацию в 10 потоков (Байкал это переварит)
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(b.get_order_info, list_of_cargo_codes))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [3/4] Байкал Сервис: ОК ({len(list_of_cargo_codes)} зак., {round(time.time() - s_bk, 2)} сек.)")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [3/4] Байкал Сервис: Заказов не обнаружено.")
    return results

def get_all_data_in_json():
    start_all = time.time()
    time_for_now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    print(f"--- НАЧАЛО ПАРАЛЛЕЛЬНОГО СБОРА ---")

    # Запускаем 4 основные задачи одновременно
    # В json_write.py замени блок получения результатов:
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_dl = executor.submit(d.orders_info)
        future_pc = executor.submit(p.fetch_detailed_data_hardcoded)
        future_vt = executor.submit(vt.get_raw_html_pages, count=2)
        future_bk = executor.submit(fetch_baikal_parallel)

        # Ждем результаты с жестким лимитом 30 секунд
        try:
            dl_curr_ord = future_dl.result(timeout=30)
            pc_curr_ord = future_pc.result(timeout=30) # Если ПЭК висит, через 30с сработает исключение
            vt_raw_html_list = future_vt.result(timeout=30)
            bc_detailed_info = future_bk.result(timeout=30)
        except Exception as e:
            print(f"\n[!] Сбор прерван по таймауту или ошибке: {e}")
            # Инициализируем пустые списки для тех, кто не успел
            dl_curr_ord = dl_curr_ord if 'dl_curr_ord' in locals() else []
            pc_curr_ord = pc_curr_ord if 'pc_curr_ord' in locals() else []
            vt_raw_html_list = vt_raw_html_list if 'vt_raw_html_list' in locals() else []
            bc_detailed_info = bc_detailed_info if 'bc_detailed_info' in locals() else []


    print("-" * 30)
    print(f"ОБЩЕЕ ВРЕМЯ ВЫПОЛНЕНИЯ: {round(time.time() - start_all, 2)} сек.")
    print("-" * 30)

    # Блок записи (твоя логика без изменений)
    try:
        combined_data = {
            "Timestamp": time_for_now,
            "Dellin": dl_curr_ord,
            "Pecom": pc_curr_ord,
            "Baikal": bc_detailed_info,
            "BSD": vt_raw_html_list,
        }

        file_path = Path("data/test_all_tk.json")
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("w", encoding='utf-8') as json_file:
            json.dump(combined_data, json_file, indent=2, sort_keys=True, ensure_ascii=False)
        print("[✓] Сбор всех 'сырых' данных завершен (/data/test_all_tk.json)")

    except Exception as e:
        print(f"Ошибка при сохранении JSON: {e}")

def main():
    get_all_data_in_json()

if __name__ == '__main__':
    main()
