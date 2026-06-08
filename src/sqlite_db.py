"""
SQLite storage backend wrapped in a class interface.
Provides `init_db()`, `insert(record)`, `fetch_rows(limit)` and other helpers
matching what the application needs.
"""
import os
import sqlite3
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class SQLiteDB:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv('DB_PATH', 'telemetry.db')

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        temperature REAL,
                        humidity INTEGER,
                        wind_speed REAL,
                        wind_dir INTEGER,
                        barometer REAL,
                        rain_rate REAL,
                        solar_rad INTEGER,
                        uv INTEGER,
                        ac_solar_w REAL,
                        house_power_w REAL,
                        net_balance REAL
                    )
                """)
                conn.commit()
                logger.info(f"SQLite DB initialized at: {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing SQLite DB: {e}")
            raise

    def insert(self, record: Dict) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO telemetry
                    (timestamp, temperature, humidity, wind_speed, wind_dir, barometer, rain_rate, solar_rad, uv, ac_solar_w, house_power_w, net_balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get('timestamp'),
                        record.get('temperature'),
                        record.get('humidity'),
                        record.get('wind_speed'),
                        record.get('wind_dir'),
                        record.get('barometer'),
                        record.get('rain_rate'),
                        record.get('solar_rad'),
                        record.get('uv'),
                        record.get('ac_solar_w'),
                        record.get('house_power_w'),
                        record.get('net_balance')
                    )
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"SQLite insert failed: {e}")
            return False

    def fetch_rows(self, limit: int = 200) -> List[sqlite3.Row]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM (
                        SELECT * FROM telemetry ORDER BY id DESC LIMIT ?
                    ) ORDER BY id ASC
                    """,
                    (limit,)
                )
                rows = cursor.fetchall()
                return rows
        except Exception as e:
            logger.error(f"SQLite fetch_rows failed: {e}")
            return []

    def fetch_statistics_daily(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        'Periodo ' || ((id - 1) / 100 + 1) as date,
                        ROUND(SUM(ac_solar_w) / 1000.0, 2) as generated_kwh,
                        ROUND(SUM(house_power_w) / 1000.0, 2) as consumed_kwh,
                        ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 1000.0, 2) as sold_excess_kwh,
                        ROUND(AVG(ac_solar_w), 1) as avg_solar_w,
                        ROUND(AVG(house_power_w), 1) as avg_consumption_w
                    FROM (
                        SELECT * FROM telemetry 
                        WHERE id > (SELECT IFNULL(MAX(id),0) - 1000 FROM telemetry)
                        ORDER BY id DESC
                    )
                    GROUP BY ((id - 1) / 100)
                    ORDER BY ((id - 1) / 100) DESC
                    LIMIT 30
                """)
                rows = cursor.fetchall()
                return rows
        except Exception as e:
            logger.error(f"SQLite fetch_statistics_daily failed: {e}")
            return []

    def fetch_statistics_monthly(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        'Atual' as month,
                        ROUND(SUM(ac_solar_w) / 1000.0, 2) as generated_kwh,
                        ROUND(SUM(house_power_w) / 1000.0, 2) as consumed_kwh,
                        ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 1000.0, 2) as sold_excess_kwh,
                        ROUND(AVG(ac_solar_w), 1) as avg_solar_w,
                        ROUND(AVG(house_power_w), 1) as avg_consumption_w
                    FROM telemetry
                """)
                rows = cursor.fetchall()
                return rows
        except Exception as e:
            logger.error(f"SQLite fetch_statistics_monthly failed: {e}")
            return []

    def fetch_summary(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Get last timestamp safely
                cursor.execute("SELECT timestamp FROM telemetry ORDER BY id DESC LIMIT 1")
                last = cursor.fetchone()

                hoje_inicio = datetime_now_str('%Y-%m-%d 00:00:00')
                hoje_fim = datetime_now_str('%Y-%m-%d 23:59:59')

                cursor.execute("""
                    SELECT 
                        ROUND(SUM(ac_solar_w) / 360000.0, 2) as generated_kwh_today,
                        ROUND(SUM(house_power_w) / 360000.0, 2) as consumed_kwh_today,
                        ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 360000.0, 2) as sold_kwh_today
                    FROM telemetry
                    WHERE timestamp >= ? AND timestamp <= ?
                """, (hoje_inicio, hoje_fim))
                day_row = cursor.fetchone()

                mes_inicio = datetime_now_str('%Y-%m-01 00:00:00')
                proximo_mes = next_month_start_str()
                cursor.execute("""
                    SELECT 
                        ROUND(SUM(ac_solar_w) / 360000.0, 2) as generated_kwh_month,
                        ROUND(SUM(house_power_w) / 360000.0, 2) as consumed_kwh_month,
                        ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 360000.0, 2) as sold_kwh_month
                    FROM telemetry
                    WHERE timestamp >= ? AND timestamp < ?
                """, (mes_inicio, proximo_mes))
                month_row = cursor.fetchone()
                return {
                    'today': {
                        'generated': day_row[0] or 0,
                        'consumed': day_row[1] or 0,
                        'sold': day_row[2] or 0
                    },
                    'month': {
                        'generated': month_row[0] or 0,
                        'consumed': month_row[1] or 0,
                        'sold': month_row[2] or 0
                    }
                }
        except Exception as e:
            logger.error(f"SQLite fetch_summary failed: {e}")
            return {'today': {'generated': 0, 'consumed': 0, 'sold': 0}, 'month': {'generated': 0, 'consumed': 0, 'sold': 0}}


def datetime_now_str(fmt='%Y-%m-%d %H:%M:%S'):
    from datetime import datetime
    return datetime.now().strftime(fmt)


def next_month_start_str():
    import datetime
    hoje = datetime.date.today()
    proximo_mes = (hoje.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return proximo_mes.strftime('%Y-%m-%d 00:00:00')
