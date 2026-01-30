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



from datetime import datetime
from pathlib import Path
import json
import requests

from api_classes import (
    BK_SECRET_KEY,
    DL_LOGIN,
    DL_PASS,
    DL_SECRET_KEY,
    PC_LOGIN,
    PC_SECRET_KEY,
    BaikalApiV2,
    DellinApiV1,
    PecomApiV1,
)


time_for_now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

p = PecomApiV1(PC_SECRET_KEY, PC_LOGIN)
d = DellinApiV1(DL_SECRET_KEY, DL_LOGIN, DL_PASS)
b = BaikalApiV2(BK_SECRET_KEY)

dl_curr_ord = d.orders_info()
pc_curr_ord = p.fetch_detailed_data_hardcoded()
bk_curr_ord = b.get_oreders_list()

list_of_cargo_codes = b.collect_cargocodes()
for i in list_of_cargo_codes:
    bc_detailed_info = b.get_order_info(i)


def get_all_data_in_json(dl, pc, bk):
    """Сбор/запись общий информации по заказам
    из трех ТК: деловые, пэк, байкал, добавление таймштампа

    :param dl: [метод отбора текущих перевозок]
    :type dl: [DellinApiV1]
    :param pc: [метод отбора текущих перевозок]
    :type pc: [PecomApiV1]
    :param bk: [метод отбора текущих перевозок]
    :type bk: [BaikalApiV2]
    """
    try:
        combined_data = {
            "Timestamp": time_for_now,
            "Dellin": dl,
            "Pecom": pc,
            "Baikal": bk,
        }

        file_path = Path("data/test_all_tk.json")
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("w", encoding='utf-8') as json_file:
            json.dump(combined_data, json_file, indent=2, sort_keys=True, ensure_ascii=False)
        print("Cargos API data was successfully saved to /data/test_all_tk.json")

    except requests.exceptions.RequestException as e:
        print(f"As error was occured during the API request: {e}")

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")

    except IOError as e:
        print(f"Error writing to file: {e}")


def main():
    get_all_data_in_json(dl_curr_ord, pc_curr_ord, bc_detailed_info)

if __name__ == '__main__':
    main()
