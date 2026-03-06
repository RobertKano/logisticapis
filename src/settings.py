# -*- coding: utf-8 -*-
# Copyright (C) 2024-2026 RobertKano
# Project: LogisticAPIs (https://github.com)

import os
from dotenv import load_dotenv

# --- ИНИЦИАЛИЗАЦИЯ ОКРУЖЕНИЯ ---
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

# --- ПУТИ К ДАННЫМ (Нормализация 2026) ---
# Определяем корневую папку данных (на уровень выше от src)
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

# 1. СЫРЫЕ данные от API (замена test_all_tk.json)
RAW_DATA_FILE = os.path.join(DATA_DIR, 'raw_api_data.json')

# 2. ТЕКУЩЕЕ СОСТОЯНИЕ для фронтенда (замена test_all_tk_processed.json)
CURRENT_STATE_FILE = os.path.join(DATA_DIR, 'current_state.json')

# 3. ПОСЛЕДНЕЕ СОСТОЯНИЕ (для сравнения и архивации)
LAST_STATE_FILE = os.path.join(DATA_DIR, 'last_active_state.json')

# 4. ПУТЬ К БУДУЩЕЙ БАЗЕ ДАННЫХ (пока не используется)
DB_PATH = os.path.join(DATA_DIR, 'cargo_system.db')

# 5. СЛУЖЕБНЫЕ ФАЙЛЫ
HISTORY_FILE = os.path.join(DATA_DIR, 'history_archive.json')
HASH_FILE = os.path.join(DATA_DIR, 'last_report_hash.txt')
LOG_FILE = os.path.join(DATA_DIR, 'process.log')

# --- НАСТРОЙКИ УВЕДОМЛЕНИЙ ---
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID", "")
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")

# --- МАППИНГ ГОРОДОВ ---
CITY_MAP = {
    "астрахань": "АСТРА",
    "санкт-петербург": "СПБ",
    "новосибирск": "НСК",
    "екатеринбург": "ЕКБ",
    "нижний новгород": "Н.НОВ",
    "ярославль": "ЯРС",
    "краснодар": "КРД",
    "ростов-на-дону": "РНД",
    "домодедово": "ДМД",
    "одинцово": "ОДИН",
    "пермь": "ПРМ",
    "казань": "КЗН",
    "челябинск": "ЧЛБ",
    "красноярск": "КРЯ",
    "москва": "МСК",
    "мытищи": "МТЩ",
    "балашиха": "БЛШ",
    "брянск": "БРН",
    "железнодорожный": "ЖД БЛШ",
    "волгоград": "ВОЛГ",
    "владивосток": "ВЛД",
    "краснокамск": "КРСКМК",
    "самара": "СМР",
}

def main():
    print(f"[Settings] DATA_DIR: {DATA_DIR}")
    print(f"[Settings] RAW_DATA_FILE: {RAW_DATA_FILE}")

if __name__ == '__main__':
    main()
