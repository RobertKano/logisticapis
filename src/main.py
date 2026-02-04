# -*- coding: utf-8 -*-
# Copyright (C) 2024-2026 RobertKano
# Project: LogisticAPIs (https://github.com)
#
# ... (Остальной текст лицензии и копирайтов) ...

import sys
import os
import logging
from datetime import datetime

# Добавляем текущую директорию в пути поиска Python, чтобы найти модули src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json_write as jw
import main_parser as mp
import notifier as nt  # Импортируем наш новый модуль нотификаций


logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), '..', 'data', 'process.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def start_app():
    print("--- ШАГ 1: Сбор и парсинг данных из API ТК ---")
    try:
        logging.info("--- Старт процесса обновления данных ---")

        # 1. Запускаем сбор данных из API (создает test_all_tk.json)
        jw.main()

        # 2. Парсим данные и создаем итоговый report_YYYY-MM-DD.json
        mp.run_main_parser()

        logging.info("--- Парсинг завершен ---")
        print("Сбор и парсинг данных завершен успешно.\n")

        # 3. Отправляем уведомление в Telegram (ШАГ 2)
        print("--- ШАГ 2: Отправка уведомлений в TG ---")
        date_str = datetime.now().strftime('%Y-%m-%d')
        # Определяем путь к свежесозданному JSON отчету
        report_path = os.path.join(os.path.dirname(__file__), '..', 'data', f"report_{date_str}.json")

        nt.send_tg_summary(report_path)

        logging.info("--- Уведомление отправлено ---")
        print("\n[✓] Весь цикл обновления завершен.")

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
        # Здесь можно добавить отправку ошибки администратору в ТГ, если интересно
        return

if __name__ == "__main__":
    start_app()

