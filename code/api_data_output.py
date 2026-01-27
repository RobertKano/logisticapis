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
