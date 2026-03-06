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


import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright
import pandas as pd
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re

current_dir = Path.cwd()

# secrets import mechanism
load_dotenv()
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

# dates for get_period method
time_for_now = datetime.now()
time_for_month_ago = time_for_now - timedelta(days=31)

# group of secrets constants
DL_SECRET_KEY = os.getenv("dl_appkey")
DL_LOGIN = os.getenv("dl_login")
DL_PASS = os.getenv("dl_password")

PC_SECRET_KEY = os.getenv("pc_appkey")
PC_LOGIN = os.getenv("pc_login")

BK_SECRET_KEY = os.getenv("bk_appkey")

VT_LOGIN = os.getenv("bsd_login")
VT_PASS = os.getenv("bsd_pass")

MT_LOGIN = os.getenv("magic_login")
MT_PASS = os.getenv("magic_pass")


class BaikalApiV2:
    """
    Baikal API fetch data base class

    :param host: main API URL
    :type host: str
    :param url_cargos_list: url for main cargo info
    :type url_cargos_list: str
    :param url_cargos_detail: url for detailed cargo info
    :type url_cargos_detail: str
    :param headers: mandatory request headers
    :type headers: dict
    """
    host = "https://api.baikalsr.ru/v2/"
    url_cargos_list = f"{host}order/list"
    url_cargos_detail = f"{host}order/detail"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }

    def __init__(self, apiKey):
        """class constructor method

        :param apiKey: string with API auth key
        :type apiKey: str
        """
        self.apiKey = apiKey
        self.basicAuth = HTTPBasicAuth(username=self.apiKey, password="")

    def get_oreders_list(self):
        """
        The main method for obtaining a list of orders, it is not detailed, it helps to
        collect order numbers and then transfer them to the get_order_info method

        {"0": "Нет данных",
        "4": "Груз принят к перевозке",
        "5": "Груз в пути",
        "6": "Груз прибыл",
        "7": "Груз на доставке",
        "10": "Груз перенаправляется на терминал",
        "11": "Груз передан в службу доставки",
        "12": "Груз прибыл в ПВЗ",
        "8": "Груз выдан",
        "9": "Груз передан в службу универсальной",
        "13": "Груз доставлен",}

        :returns: the JSON object obtained via the url_cargos_list link uses a data dictionary when requested, which stores information about statuses and date ranges.
        :rtype: dict
        """
        data = {
            "date": {
                "from": str(time_for_month_ago.isoformat(timespec="seconds")),
                "to": str(time_for_now.isoformat(timespec="seconds")),
            },
            "status": [0, 4, 5, 6, 7, 10, 11, 12, 9, 8, 13],
        }
        r = requests.post(
            self.url_cargos_list,
            data=json.dumps(data),
            auth=self.basicAuth,
            headers=self.headers,
        )
        return json.loads(r.text)

    def collect_cargocodes(self):
        """
        collects transport numbers

        :returns: the list contains lines with transport numbers
        :rtype: list
        """

        list_of_cargo_codes = []

        bc_current_orders = self.get_oreders_list()
        for i in bc_current_orders['orderList']:
            list_of_cargo_codes.append(i['number'])

        return list_of_cargo_codes

    def get_order_info(self, number):
        """get detailed info to output in main json file

        :param number: string with the transport number
        :type number: str
        :returns: json dict with detailed cargo info
        :rtype: dict
        """

        data = {"number": number}
        r = requests.post(
            self.url_cargos_detail,
            data=json.dumps(data),
            auth=self.basicAuth,
            headers=self.headers,
        ).json()
        return r

    def __str__(self):
        """class description method

        :returns: info about class
        :rtype: {str}
        """
        return "fetch data from Baikal API"


class PecomApiV1:
    host = "https://kabinet.pecom.ru/api/v1/"
    url_login = f"{host}auth/"
    url_profile = f"{host}auth/profiledata/"
    url_cargos_list = f"{host}cargos/list/"
    url_cargos_detail = f"{host}cargos/details/"
    url_cargos_status = f"{host}cargos/status/"

    cargoStatus = ["В пути", "Прибыл", "Выдан на доставку"]

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }

    def __init__(self, appKey, login=None):
        self.appKey = appKey
        self.login = login
        self.basicAuth = HTTPBasicAuth(self.login, self.appKey)

    def orders_list(self):
        r = requests.post(
            self.url_cargos_list,
            data=json.dumps(self.get_period()),
            auth=self.basicAuth,
            headers=self.headers,
            timeout=20
        )
        # return r.request.body, r.request.headers, self.url_cargos_list
        return r.json()

    def collect_cargocodes(self):
        list_of_cargo_codes = []
        try:
            pc_current_orders = self.orders_list()

            # ПРОВЕРКА: Если сервер прислал не JSON или ошибку
            if not pc_current_orders or 'cargos' not in pc_current_orders:
                print("[Pecom] Ошибка: Список грузов пуст или некорректен.")
                return []

            for i in pc_current_orders['cargos']:
                # Защита от битых записей внутри списка
                if i and 'code' in i:
                    list_of_cargo_codes.append(i['code'])
        except Exception as e:
            print(f"[Pecom Error in collect]: {e}")

        return list_of_cargo_codes

    def order_info(self, cargoCode):
        data = {"cargoCode": cargoCode}
        return requests.post(
            self.url_cargos_detail,
            data=json.dumps(data),
            auth=self.basicAuth,
            headers=self.headers,
            timeout=20
        ).json()

    def get_period(self):
        period = {}
        period["dateBegin"] = str(time_for_month_ago.strftime("%Y-%m-%d"))
        period["dateEnd"] = str(time_for_now.strftime("%Y-%m-%d"))
        return period

    def fetch_detailed_data(self, cargoCodes):
        """Метод возвращает детальную информацию о перевозке
        на вход получая список из номеров перевозок

        [description]
        :param cargoCodes: список
        :type cargoCodes: list
        :returns: json объект
        :rtype: {json object}
        """
        data = {"cargoCodes": cargoCodes}
        r = requests.post(
            self.url_cargos_status,
            data=json.dumps(data),
            auth=self.basicAuth,
            headers=self.headers,
        )
        return r.json()

    def fetch_detailed_data_hardcoded(self):
        """Метод возвращает детальную информацию о перевозке
        на вход получая список из номеров перевозок

        [description]
        :param cargoCodes: список
        :type cargoCodes: list
        :returns: json объект
        :rtype: {json object}
        """
        data = {"cargoCodes": self.collect_cargocodes()}
        r = requests.post(
            self.url_cargos_status,
            data=json.dumps(data),
            auth=self.basicAuth,
            headers=self.headers,
            timeout=20
        )
        return r.json()


class DellinApiV1:
    host = "https://api.dellin.ru"

    url_orders = "%s/v3/orders.json" % host
    url_login = "%s/v1/customers/login.json" % host

    headers = {"Content-Type": "application/json"}

    def __init__(self, appKey, login=None, password=None):
        self.appKey = appKey
        self.sessionID = None
        if login and password:
            self.auth(login, password)

    def auth(self, login, password):
        auth_data = {"login": login, "password": password}
        auth_data.update(self.public_auth())
        r = requests.post(
            self.url_login, data=json.dumps(auth_data), headers=self.headers
        )
        self.sessionID = r.json()["sessionID"]

    def public_auth(self):
        return {
            "appKey": self.appKey,
        }

    def customers_auth(self):
        return {
            "appKey": self.appKey,
            "sessionID": self.sessionID,
        }

    def order_info(self, docIds):
        data = {"docIds": docIds}
        data.update(self.customers_auth())
        return requests.post(
            self.url_orders, data=json.dumps(data), headers=self.headers
        ).json()

    # def orders_info(self):
    #     data = {
    #         "states":
    #             [
    #                 "inway",
    #                 "arrived",
    #                 "warehousing",
    #                 "delivery",
    #                 "finished"
    #             ]
    #     }
    #     data.update(self.customers_auth())
    #     return requests.post(
    #         self.url_orders, data=json.dumps(data), headers=self.headers
    #     ).json()

    def orders_info(self):
        # Вычисляем дату: 30 дней назад
        # Формат должен быть "ГГГГ-ММ-ДД ЧЧ:ММ" согласно документации
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M')

        data = {
            "states": [
                "inway",
                "arrived",
                "warehousing",
                "delivery",
                "received",
                "finished"
            ],
            # Добавляем фильтр по дате начала периода
            "dateStart": thirty_days_ago
        }

        data.update(self.customers_auth())

        r = requests.post(
            self.url_orders,
            data=json.dumps(data),
            headers=self.headers
        )
        return r.json()


class VitekaApiV1:
    host = "https://123789.ru"
    url_login = f"{host}/login"
    url_orders = f"{host}/cabinet/orders"

    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        })

    def auth(self, retries=3):
        """Пытаемся войти до 3-х раз с огромным таймаутом"""
        for attempt in range(1, retries + 1):
            try:
                # Огромный таймаут 40 секунд
                r_init = self.session.get(self.url_login, timeout=40)
                soup = BeautifulSoup(r_init.text, 'html.parser')
                token_tag = soup.find('input', {'name': '_token'})
                if not token_tag: continue

                payload = {
                    "_token": token_tag['value'],
                    "login": self.login,
                    "password": self.password,
                    "remember": "on"
                }

                r_post = self.session.post(
                    self.url_login,
                    data=payload,
                    headers={"Referer": self.url_login},
                    timeout=40
                )

                if "cabinet" in r_post.url or r_post.status_code == 200:
                    print(f"[Viteka] Вход выполнен с попытки {attempt}")
                    return True
            except Exception as e:
                print(f"[Viteka] Попытка {attempt} не удалась: {e}")
                import time
                time.sleep(2) # Пауза перед ретраем
        return False

    def get_raw_html_pages(self, count=2):
        if not self.auth():
            print("[Viteka] Ошибка: Все попытки авторизации провалены.")
            return []

        pages = []
        for p in range(1, count + 1):
            try:
                # Тоже увеличиваем до 40с
                r = self.session.get(f"{self.url_orders}?page={p}", timeout=40)
                if r.status_code == 200:
                    pages.append(r.text)
                import time
                time.sleep(1.5)
            except Exception as e:
                print(f"[Viteka] Ошибка на странице {p}: {e}")
        return pages


class MagicTransAPI:
    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.name = "Magic"

    def get_raw_data(self):
        """Авторизуется через JS-инъекцию и скачивает Excel из ЛК"""
        print(f"[{self.name}] --- ЗАПУСК МОНИТОРИНГА (FINAL) ---")

        with sync_playwright() as p:
            # Для стабильности в продакшене лучше headless=True,
            # но для финального теста можешь оставить False
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                # 1. ШАГ: ЛОГИН
                print(f"[{self.name}] 1. Переход на страницу логина...")
                page.goto("https://magic-trans.ru", timeout=60000)
                page.wait_for_timeout(3000)

                print(f"[{self.name}] 2. Принудительный ввод данных через JS...")
                page.evaluate(f"document.getElementById('login-name').value = '{self.login}'")
                page.evaluate(f"document.getElementById('password').value = '{self.password}'")

                print(f"[{self.name}] 3. Силовой клик (JS Trigger)...")
                page.evaluate("document.getElementById('login').dispatchEvent(new MouseEvent('click', {bubbles: true}))")

                # Ждем прогрузки сессии
                page.wait_for_timeout(10000)

                # 2. ШАГ: ПЕРЕХОД В ЗАКАЗЫ (Где кнопка Excel)
                print(f"[{self.name}] 4. Переход в раздел заказов...")
                page.goto("https://magic-trans.ru", timeout=60000, wait_until="networkidle")

                # Проверка: если URL не заказы, пробуем еще раз
                if "/personal/orders/" not in page.url:
                    page.goto("https://magic-trans.ru/personal/orders/", timeout=60000)

                # 3. ШАГ: СКАЧИВАНИЕ
                print(f"[{self.name}] 5. Ожидание выгрузки Excel...")
                try:
                    with page.expect_download(timeout=60000) as download_info:
                        # Используем селектор из твоего HTML-листинга
                        page.evaluate("document.querySelector('a.excel_btn').click()")

                    download = download_info.value
                    # Сохраняем в корень data, как ты просил
                    temp_path = os.path.join("data", "magic_tmp.xlsx")
                    download.save_as(temp_path)
                    print(f"[{self.name}] ✅ Файл получен успешно.")

                    browser.close()
                    return self._parse_excel(temp_path)

                except Exception as e:
                    print(f"[{self.name}] ❌ Ошибка скачивания: {e}")
                    page.screenshot(path="data/magic_orders_error.png")
                    browser.close()
                    return []

            except Exception as e:
                print(f"[{self.name}] 🔥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
                if 'browser' in locals(): browser.close()
                return []

    def _parse_excel(self, file_path):
        """Парсинг Excel строго по списку колонок из консоли"""
        try:
            # Читаем Excel
            df = pd.read_excel(file_path, engine='openpyxl')

            # Мы вывели список колонок, теперь используем их точные имена
            results = []
            for _, row in df.iterrows():
                # 1. Номер груза (Ключевой ID)
                cargo_id = str(row.get('Номер груза', '')).strip()
                if not cargo_id or cargo_id == 'nan':
                    continue

                # 2. Параметры (Обрати внимание на 'Обьем' через мягкий знак)
                p_str = f"{row.get('Количество мест', 0)}М | {row.get('Вес, кг', 0)}КГ | {row.get('Обьем, м3', 0)}М3"

                # 3. Сумма (Сумма, руб.)
                raw_price = str(row.get('Сумма, руб.', '0')).replace(',', '.').replace(' ', '')
                total_price = float(''.join(c for c in raw_price if c.isdigit() or c == '.') or 0.0)

                item = {
                    "tk": "МАДЖИК",
                    "id": cargo_id,
                    "sender": str(row.get('Отправитель', 'Н/Д')),
                    "recipient": str(row.get('Получатель', 'Н/Д')),
                    "route": str(row.get('Маршрут перевозки', 'Н/Д')),
                    "status": str(row.get('Статус', 'Н/Д')).upper(),
                    "params": p_str,
                    "arrival": str(row.get('Ориентировочная дата прибытия', 'Н/Д')),
                    "payment": str(row.get('Статус оплаты', 'Н/Д')),
                    "total_price": total_price,
                    "payer_type": "recipient" if "ЮЖНЫЙ ФОРПОСТ" in str(row.get('Плательщик', '')) else "sender",
                    "is_manual": False
                }
                results.append(item)

            if os.path.exists(file_path):
                os.remove(file_path)

            print(f"[{self.name}] Парсинг завершен. Найдено строк: {len(results)}")
            return results

        except Exception as e:
            print(f"[{self.name}] ❌ Ошибка обработки Excel: {e}")
            return []


if __name__ == "__main__":
    # Если данные уже в окружении (MT_LOGIN / MT_PASS), запустится сразу
    if 'MT_LOGIN' in globals() and 'MT_PASS' in globals():
        magic = MagicTransAPI(MT_LOGIN, MT_PASS)
        data = magic.get_raw_data()
        print(f"\n[Test] Найдено: {len(data)} грузов")
        for c in data[:3]:
            print(f"-> {c['id']} | {c['status']} | {c['total_price']} руб.")
