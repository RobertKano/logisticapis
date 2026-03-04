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
                    created_at TIMESTAMP,          -- Дата первого появления
                    updated_at TIMESTAMP           -- Дата последнего обновления
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
        """Использует COALESCE, чтобы created_at записывался только 1 раз"""
        p_val, w_val, v_val = self._parse_params(item.get('params', ''))
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Важное изменение: created_at = COALESCE(cargo.created_at, excluded.created_at)
            # Это сохраняет самую первую дату записи
            cursor.execute('''
                INSERT INTO cargo (
                    id, tk, sender, recipient, route,
                    places, weight, volume,
                    status, arrival, payment, total_price,
                    payer_type, is_archived, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    tk=excluded.tk,
                    status=excluded.status,
                    arrival=excluded.arrival,
                    payment=excluded.payment,
                    total_price=excluded.total_price,
                    places=excluded.places,
                    weight=excluded.weight,
                    volume=excluded.volume,
                    is_archived=excluded.is_archived,
                    created_at=COALESCE(cargo.created_at, excluded.created_at),
                    updated_at=excluded.updated_at
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

if __name__ == "__main__":
    pass
