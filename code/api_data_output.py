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

import json_write as jw
import api_data_processing as adp
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
DELIM = "-" * 83 + "\n"
DELIM_FLAG = False

d = DellinApiV1(DL_SECRET_KEY, DL_LOGIN, DL_PASS)
p = PecomApiV1(PC_SECRET_KEY, PC_LOGIN)
b = BaikalApiV2(BK_SECRET_KEY)

# Для отображения списка заказов
dl_current_orders = d.orders_info()
# pc_current_orders = p.fetch_detailed_data_hardcoded()
pc_current_orders = p.orders_list()
bk_current_orders = b.get_oreders_list()

file_path = Path("data/chunk.txt")
file_path.parent.mkdir(parents=True, exist_ok=True)

jw.main()

with file_path.open("w", encoding="utf-8") as f:
    print()
    f.write(f"Timestamp: {time_for_now}\n")

    f.write(f"{'='*38}ДЕЛОВЫЕ{'='*38}\n")
    f.write(adp.dl_approaching_orders(dl_current_orders))
    f.write(DELIM)

    f.write(f"{'='*40}ПЭК{'='*40}\n")
    f.write(adp.pc_approaching_orders(pc_current_orders))  # <----------------

    f.write(f"{'='*39}БАЙКАЛ{'='*38}\n")
    f.write(adp.bc_approaching_orders(bk_current_orders))
    f.write(DELIM)

    print("Запись в файл ../data/chunk.txt закончена")
