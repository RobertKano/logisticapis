# -*- coding: utf-8 -*-
import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Импорт путей и констант
from settings import RAW_DATA_FILE
from api_classes import (
    BK_SECRET_KEY, DL_LOGIN, DL_PASS, DL_SECRET_KEY,
    PC_LOGIN, PC_SECRET_KEY, VT_LOGIN, VT_PASS,
    MT_LOGIN, MT_PASS, # Твои новые константы
    BaikalApiV2, DellinApiV1, PecomApiV1, VitekaApiV1, MagicTransAPI
)

# Инициализация объектов ТК
p = PecomApiV1(PC_SECRET_KEY, PC_LOGIN)
d = DellinApiV1(DL_SECRET_KEY, DL_LOGIN, DL_PASS)
b = BaikalApiV2(BK_SECRET_KEY)
vt = VitekaApiV1(VT_LOGIN, VT_PASS)
mt = MagicTransAPI(MT_LOGIN, MT_PASS) # Объект для Magic Trans

def fetch_baikal_parallel():
    """Специфический сборщик для Байкала (использует свои потоки внутри)"""
    s_bk = time.time()
    list_of_cargo_codes = b.collect_cargocodes()
    results = []
    if list_of_cargo_codes:
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(b.get_order_info, list_of_cargo_codes))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [3/5] Байкал Сервис: ОК ({len(list_of_cargo_codes)} зак., {round(time.time() - s_bk, 2)} сек.)")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [3/5] Байкал Сервис: Заказов не обнаружено.")
    return results

def get_all_data_in_json():
    start_all = time.time()
    time_for_now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    print("\n" + "="*50)
    print(f"🚀 СБОР ДАННЫХ ОТ {time_for_now}")
    print("="*50)

    # 1. ПАРАЛЛЕЛЬНЫЙ СБОР (API-based ТК)
    print("--- ШАГ 1: Параллельный сбор (ДЛ, ПЭК, БСД, Байкал) ---")
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_dl = executor.submit(d.orders_info)
        future_pc = executor.submit(p.fetch_detailed_data_hardcoded)
        future_vt = executor.submit(vt.get_raw_html_pages, count=2)
        future_bk = executor.submit(fetch_baikal_parallel)

        try:
            dl_curr_ord = future_dl.result(timeout=45)
            pc_curr_ord = future_pc.result(timeout=45)
            vt_raw_html_list = future_vt.result(timeout=45)
            bc_detailed_info = future_bk.result(timeout=45)
        except Exception as e:
            print(f"⚠️ Ошибка в параллельном блоке: {e}")
            dl_curr_ord = locals().get('dl_curr_ord', [])
            pc_curr_ord = locals().get('pc_curr_ord', [])
            vt_raw_html_list = locals().get('vt_raw_html_list', [])
            bc_detailed_info = locals().get('bc_detailed_info', [])

    # 2. ПОСЛЕДОВАТЕЛЬНЫЙ СБОР (Browser-based ТК: Magic Trans)
    # Запускаем отдельно, так как Playwright требует стабильного контекста
    print("\n--- ШАГ 2: Эмуляция браузера (Magic Trans) ---")
    try:
        mt_data = mt.get_raw_data()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [5/5] Magic Trans: ОК ({len(mt_data)} зак.)")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [5/5] Magic Trans: ОШИБКА ({e})")
        mt_data = []

    print("-" * 50)
    print(f"ОБЩЕЕ ВРЕМЯ РАБОТЫ: {round(time.time() - start_all, 2)} сек.")
    print("-" * 50)

    # 3. СОХРАНЕНИЕ И ВАЛИДАЦИЯ
    try:
        combined_data = {
            "Timestamp": time_for_now,
            "Dellin": dl_curr_ord,
            "Pecom": pc_curr_ord,
            "Baikal": bc_detailed_info,
            "BSD": vt_raw_html_list,
            "Magic": mt_data # Наш новый блок данных
        }

        # Запись в файл
        with open(RAW_DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, sort_keys=True, ensure_ascii=False)

        # ПРОВЕРКА СОХРАНЕНИЯ
        if os.path.exists(RAW_DATA_FILE):
            size = os.path.getsize(RAW_DATA_FILE) / 1024
            print(f"✅ ФАЙЛ ОБНОВЛЕН: {RAW_DATA_FILE} ({round(size, 1)} KB)")

            # Проверяем наполнение Magic в файле
            if mt_data:
                print("✨ Данные Magic Trans успешно интегрированы в JSON.")
            else:
                print("ℹ️ Внимание: Блок Magic пуст (нет новых грузов или ошибка).")
        else:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Файл {RAW_DATA_FILE} не создан!")

    except Exception as e:
        print(f"❌ Ошибка при финализации JSON: {e}")

def main():
    get_all_data_in_json()

if __name__ == '__main__':
    main()
