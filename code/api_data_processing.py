#  processing of received data
from datetime import datetime


from api_classes import (
    BaikalApiV2,
    BK_SECRET_KEY,
    PC_LOGIN,
    PC_SECRET_KEY,
    PecomApiV1,
)


b = BaikalApiV2(BK_SECRET_KEY)
bk_current_orders = b.get_oreders_list()
detailed_info = b.get_order_info("ПД-0242284")


def dl_approaching_orders(dl_current_orders):
    # DELIM = '\n' + "-" * 51 + '\n'
    DELIM2 = "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    s = ""
    table = {False: "Не оплачено", True: "Оплачено"}
    for i in dl_current_orders["orders"]:
        sender = (
            i["sender"]["name"]
            .upper()
            .replace("АО", "")
            .replace("ООО", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )
        receiver = (
            i["receiver"]["name"]
            .upper()
            .replace("АО", "")
            .replace("ООО", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )
        orderID = i["orderId"]

        arrivalPlanDateTime = i["orderDates"]["arrivalToOspReceiver"]
        sendingDateTime = i["orderDates"]["derivalFromOspSender"]

        if orderID == "2000071002028":
            continue
        else:
            if i["isPaid"]:
                i["isPaid"] = table[True]
            else:
                i["isPaid"] = table[False]
            if len(dl_current_orders["orders"]) > 1:
                s += f"\t{i['stateName']} - {i['progressPercent']}% - Груз для {receiver}\n\t\t{sender} ({orderID})\n\t\t\t{i['freight']['places']} м, {int(float(i['freight']['weight']))} кг, {i['freight']['volume']} м3\n(Контакт отправителя - {i['sender']['contacts']}|Контакт получателя - {i['receiver']['contacts']}|{i['isPaid']} - {i['payer']['name']} - {i['totalSum']}р)\n(Город отправителя: {i['derival']['city']}|дата отправления: {sendingDateTime}|ориентир прибытия: {arrivalPlanDateTime})\n{DELIM2}\n"
            else:
                s += f"{i['stateName']} ({i['stateDate']}) - {i['orderId']} - {i['progressPercent']}%\n\tоформлен {i['orderedAt']}\n\tот: {i['sender']['name']} - {i['sender']['contacts']}\n\tдля: {i['receiver']['name']} - {i['receiver']['contacts']}\n\t\t{i['freight']['places']} м, {i['freight']['weight']} кг, {i['freight']['volume']} м3\nОриентировочная дата прибытия: {i['orderDates']['arrivalToOspReceiver']}\nПлатное хранение начнется: {i['orderDates']['warehousing']}\n{i['isPaid']} - {i['payer']['name']} - {i['totalSum']}р\n"
    return s.upper()

p = PecomApiV1(PC_SECRET_KEY, PC_LOGIN)
# pc_orders_list = p.collect_cargocodes()
# pc_orders_list = p.fetch_detailed_data_hardcoded()
pc_current_orders = p.orders_list()
def pc_approaching_orders(pc_current_orders):
    DELIM = "\n" + "-" * 83 + "\n"
    cargoStatus = [
        "В пути",
        "Прибыл",
        "Принят к перевозке",
        "Выдан на доставку",
        "Аннулировано до приемки груза",
        "Заявка на забор зарегистрирована",
        "Ожидается передача груза от отправителя",
        "Принят на ПВЗ",
        "Возвращен отправителю",
        "Оформлен",
        "В пути на терминал",
        "Прибыл частично",
        "Разгружается. Ожидайте оповещения",
        "Выполняется адресная доставка",
        "Отправлен на возврат",
        "Утилизирован",
        "Изъят на таможне",
        "Возврат груза отправителю",
        # "Выдан получателю",
    ]
    s = ""
    for i in pc_current_orders["cargos"]:

        sender = (
            i["senderTitle"]
            .upper()
            .replace("ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ", "")
            .replace("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )

        receiver = (
            i["receiverTitle"]
            .upper()
            .replace("ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ", "")
            .replace("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )
        code = i["code"]

        payment_info_list = []
        detailed_orders_info = p.fetch_detailed_data(code)
        for x in detailed_orders_info['cargos']:
            for y in (x['services']['items']):
                payment_info = dict(
                    name=y['description'],
                    sum=y['price'],
                    payer=y['payerName'],
                    payment=y['paid'],
                )
                payment_info_list.append(payment_info)

        sendingDateTime = i["sendingDateTime"]
        arrivalPlanDateTime = datetime.strptime(
            i["arrivalPlanDateTime"][:-9], "%Y-%m-%d"
        ).strftime("%d-%m-%Y")

        if i["cargoStatus"] in cargoStatus:
            s += f"\t{i['cargoStatus']}\n\t\t{sender} ({code})\n\t\t\t{i['positionsCount']} м, {int(float(i['weight']))} кг, {i['volume']} м3\n(дата отправления: {sendingDateTime} | ориентир прибытия: {arrivalPlanDateTime})\n(груз для: {receiver})\n(информация об оплате: {payment_info_list}){DELIM}"
        else:
            s = f"активных грузов нет{DELIM}"
    return s.upper()


def bc_approaching_orders(bk_current_orders):
    # DELIM = '\n' + "-" * 51 + '\n'
    DELIM2 = "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    s = ""
    for i in bk_current_orders["orderList"]:
        # Детальная информация по отдельным перевозкам для интеграции в
        # общий вывод
        detailed_orders_info = b.get_order_info(i["number"])
        # print(detailed_orders_info['cargoList'][0]['cargo'])

        # дата отправления
        departure_date = datetime.strptime(i["date"][:-9], "%Y-%m-%d").strftime("%d-%m-%Y")
        # datetime.strptime(i["date"][:-9], "%Y-%m-%d").strftime("%d-%m-%Y")

        if i["cargoList"][0]["dateArrivalPlane"]:
            arrival_date = datetime.strptime(i["cargoList"][0]["dateArrivalPlane"][:-9], "%Y-%m-%d").strftime("%d-%m-%Y")
        else:
            print('There is no arrival date in the data for one of the cargoes from Baikal.')
            arrival_date = 'None'

        # дата получения
        # try:
        #     # comment: груз без прописанной даты прибытия, обычно пакет документов
        #     arrival_date = datetime.strptime(i["cargoList"][0]["dateArrivalPlane"][:-9], "%Y-%m-%d").strftime("%d-%m-%Y")
        # except Exception:
        #     arrival_date = 'none'
        #     print(arrival_date)
        #     continue
        # end try

        # наименование отправителя
        sender = (
            i["cargoList"][0]["consignor"]["name"]
            .upper()
            .replace("АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "")
            .replace("ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace("ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )

        if sender == "ОБОСОБЛЕННОЕ-ПОДРАЗДЕЛЕНИЕ--КПД-В-Г.-РОСТОВ-НА-ДОНУ":
            sender = "КПД"

        # наименование получателя
        receiver = (
            i["cargoList"][0]["consignee"]["name"]
            .upper()
            .replace("АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "")
            .replace("ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace("ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )

        # города отправления и назначения
        dep_state = i["cargoList"][0]["departure"]["name"]
        dest_state = i["cargoList"][0]["destination"]["name"]

        # номер квитанции
        receipt_number = i["number"]
        # номер груза
        cargo_number = i["cargoList"][0]["number"]
        # трек номер
        track_number = i["trackingnumber"]
        # (f"({receipt_number}|{cargo_number}|{track_number})\n")

        # статус груза
        cargo_status = i["cargoList"][0]["status"]["name"]
        cargo_status_id = i["cargoList"][0]["status"]["id"]

        # параметры груза
        places = detailed_orders_info["cargoList"][0]["cargo"]["places"]
        weight = detailed_orders_info["cargoList"][0]["cargo"]["weight"]
        volume = detailed_orders_info["cargoList"][0]["cargo"]["volume"]
        # weight = i["cargoList"][0]["weightcargo"]
        # volume = i["cargoList"][0]["cubaturecargo"]
        character = detailed_orders_info["cargoList"][0]["cargo"]["сharacter"]["name"]
        # f"{places} м, {int(float(weight))} кг, {volume} м3\n"

        # информация об оплате
        # paid_sum = i['paid'] # оплаченная сумма
        total_sum = i["total"]
        payer = (
            detailed_orders_info["cargoList"][0]["services"][0]["payer"]["name"]
            .upper()
            .replace("АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "")
            .replace("ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace("ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО", "")
            .replace('"', "")
            .strip()
            .replace(" ", "-")
        )

        if payer == "ОБОСОБЛЕННОЕ-ПОДРАЗДЕЛЕНИЕ--КПД-В-Г.-РОСТОВ-НА-ДОНУ":
            payer = "КПД"

        paidStatus = detailed_orders_info["paidStatus"]

        s += f"\t{cargo_status}[{cargo_status_id}] - для {receiver}\n\t\t{sender} ({receipt_number}|{cargo_number}|{track_number})\n\t\t\t{places} м, {int(float(weight))} кг, {volume} м3\n(характер груза: {character})\n(направление: {dep_state} -> {dest_state} | плательщик {payer}, стоимость перевозки: {total_sum}, статус оплаты: {paidStatus})\n(дата отправления: {departure_date} | ориентир прибытия: {arrival_date} )\n{DELIM2}\n"

    return s.upper()


def main():
    print(pc_approaching_orders(pc_current_orders))

if __name__ == "__main__":
    main()
