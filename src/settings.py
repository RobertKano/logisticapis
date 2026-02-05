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



# Constants, utility functions and variables for project
import os

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'history_archive.json')
LAST_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'last_active_state.json')
HASH_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'last_report_hash.txt')
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'process.log')

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
