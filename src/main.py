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

import sys
import os
import logging
from datetime import datetime

# Добавляем текущую директорию в пути поиска Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json_write as jw
import main_parser as mp # импортируем наш красивый парсер


logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), '..', 'data', 'process.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def start_app():
    print("--- ШАГ 1: Сбор данных из API ТК ---")
    try:
        # Запускаем скрипт, который стучится в API и пишет test_all_tk.json
        logging.info("--- Старт процесса обновления данных ---")
        jw.main()
        mp.run_main_parser()
        logging.info("--- Обновление завершено успешно ---")
        print("Сбор данных завершен успешно.\n")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
        return

if __name__ == "__main__":
    start_app()

