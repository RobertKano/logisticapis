import os
from pathlib import Path
import json
from datetime import datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

current_dir = Path.cwd()

# secrets import mechanism
load_dotenv()
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

# dates for get_period method
time_for_now = datetime.now()
time_for_month_ago = time_for_now - timedelta(days=31)
# time_for_month_ago = time_for_now - timedelta(weeks=5)

# group of secrets constants
DL_SECRET_KEY = os.getenv("dl_appkey")
DL_LOGIN = os.getenv("dl_login")
DL_PASS = os.getenv("dl_password")

PC_SECRET_KEY = os.getenv("pc_appkey")
PC_LOGIN = os.getenv("pc_login")

BK_SECRET_KEY = os.getenv("bk_appkey")


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
            "status": [0, 4, 5, 6, 7, 10, 11, 12, 9],
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
        )
        # return r.request.body, r.request.headers, self.url_cargos_list
        return r.json()

    def collect_cargocodes(self):
        list_of_cargo_codes = []

        pc_current_orders = self.orders_list()

        for i in pc_current_orders['cargos']:
            list_of_cargo_codes.append(i['code'])

        return list_of_cargo_codes

    def order_info(self, cargoCode):
        data = {"cargoCode": cargoCode}
        return requests.post(
            self.url_cargos_detail,
            data=json.dumps(data),
            auth=self.basicAuth,
            headers=self.headers,
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

    def orders_info(self):
        data = {"states": ["inway", "arrived", "warehousing", "delivery"]}
        data.update(self.customers_auth())
        return requests.post(
            self.url_orders, data=json.dumps(data), headers=self.headers
        ).json()


def main():
    b = BaikalApiV2(BK_SECRET_KEY)

    bk_curr_ord = b.get_oreders_list()

    print(type(bk_curr_ord))

if __name__ == '__main__':
    main()
