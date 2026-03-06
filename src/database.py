# -*- coding: utf-8 -*-
import sqlite3
import os
import re
from datetime import datetime
try:
    from src.settings import DB_PATH
except ImportError:
    from settings import DB_PATH


class CargoDB:
    def __init__(self):
        self.init_db()
        self.init_tasks_table()

    def get_connection(self):
        return sqlite3.connect(DB_PATH)

    def init_db(self):
        """Добавлено поле created_at для корректного расчета сроков"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cargo (
                    id TEXT PRIMARY KEY,
                    tk TEXT NOT NULL,
                    sender TEXT,
                    recipient TEXT,
                    route TEXT,
                    places INTEGER DEFAULT 0,
                    weight REAL DEFAULT 0.0,
                    volume REAL DEFAULT 0.0,
                    status TEXT,
                    arrival DATE,
                    payment TEXT,
                    total_price REAL DEFAULT 0.0,
                    payer_type TEXT,
                    is_archived INTEGER DEFAULT 0,
                    archived_at TIMESTAMP,
                    created_at TIMESTAMP,          -- Дата первого появления
                    updated_at TIMESTAMP           -- Дата последнего обновления
                )
            ''')
            conn.commit()

    def init_tasks_table(self):
        """Создает расширенную таблицу для задач водителя и финансовых расчетов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS driver_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_date DATE NOT NULL,          -- Дата (ГГГГ-ММ-ДД)
                    task_time TEXT,                   -- Время (ЧЧ:ММ)
                    title TEXT NOT NULL,              -- Название (н-р, "Доставка ООО Вектор")
                    description TEXT,                 -- Комментарий (н-р, "Подняться на 2 этаж")

                    -- ГЕОГРАФИЯ И КОНТАКТЫ --
                    address TEXT,                     -- Куда ехать
                    contact_info TEXT,                -- Имя и телефон на месте

                    -- СВЯЗКА С ОСНОВНОЙ БАЗОЙ (Опционально) --
                    cargo_id TEXT,                    -- № накладной, если забор из ТК

                    -- ФИНАНСОВЫЙ БЛОК --
                    payment_amount REAL DEFAULT 0.0,  -- Сумма (руб)
                    payment_type TEXT,                -- 'to_pay' (мы платим), 'to_collect' (берем с клиента), 'none'

                    -- СЛУЖЕБНЫЕ ПОЛЯ --
                    priority INTEGER DEFAULT 1,       -- 0-Low, 1-Normal, 2-High
                    task_type TEXT DEFAULT 'once',    -- 'routine' (шаблон) или 'once' (разовая)
                    is_completed INTEGER DEFAULT 0,    -- 0-План, 1-Выполнено
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def _parse_params(self, params_str):
        if not params_str or not isinstance(params_str, str):
            return 0, 0.0, 0.0
        p = re.search(r'(\d+)\s*М', params_str, re.I)
        w = re.search(r'([\d.]+)\s*КГ', params_str, re.I)
        v = re.search(r'([\d.]+)\s*М3', params_str, re.I)
        places = int(p.group(1)) if p else 0
        weight = float(w.group(1)) if w else 0.0
        volume = float(v.group(1)) if v else 0.0
        return places, weight, volume

    def upsert_cargo(self, item, is_archived=0):
        """Обновляет updated_at ТОЛЬКО при смене статуса"""
        p_val, w_val, v_val = self._parse_params(item.get('params', ''))
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cargo (
                    id, tk, sender, recipient, route,
                    places, weight, volume,
                    status, arrival, payment, total_price,
                    payer_type, is_archived, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    tk=excluded.tk,
                    sender=excluded.sender,
                    recipient=excluded.recipient,
                    route=excluded.route,
                    arrival=excluded.arrival,
                    payment=excluded.payment,
                    total_price=excluded.total_price,
                    places=excluded.places,
                    weight=excluded.weight,
                    volume=excluded.volume,
                    is_archived=excluded.is_archived,
                    created_at=COALESCE(cargo.created_at, excluded.created_at),

                    -- ВАЖНО: Обновляем время только если статус ИЗМЕНИЛСЯ
                    updated_at = CASE
                        WHEN cargo.status = excluded.status THEN cargo.updated_at
                        ELSE excluded.updated_at
                    END
            ''', (
                item.get('id'), item.get('tk'), item.get('sender'),
                item.get('recipient'), item.get('route'),
                p_val, w_val, v_val,
                item.get('status'), item.get('arrival'), item.get('payment'),
                float(item.get('total_price', 0) or 0.0),
                item.get('payer_type'), is_archived,
                now, now
            ))
            conn.commit()


    def archive_stuck_bsd(self):
        """
        Авто-архивация БСД: если статус 'Прибыл в город...' висит > 28 часов,
        считаем груз полученным и убираем с главной.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1.2 дня = примерно 28-29 часов (запас на случай задержки выгрузки)
            cursor.execute("""
                UPDATE cargo
                SET
                    status = 'Выдан (Авто)',
                    archived_at = CURRENT_TIMESTAMP
                WHERE tk = 'БСД'
                  AND status LIKE '%Прибыл в город назначения%'
                  AND archived_at IS NULL
                  AND (julianday('now') - julianday(updated_at)) > 1.2
            """)
            affected = cursor.rowcount
            if affected > 0:
                conn.commit()
                print(f"📦 [БСД] Авто-архивация: {affected} грузов перенесено в архив.")
            return affected


if __name__ == "__main__":
    pass
