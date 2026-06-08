"""
Optional Oracle AI-Oracle DB integration helper.

This module tries to use the Python `oracledb` package to connect to
an Oracle database (optionally using an Oracle Wallet). If the driver
is not available or the configuration is missing the functions are
no-ops but will log helpful messages.
"""
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

ORACLE_ENABLED = os.getenv('ORACLE_DB_ENABLED', 'true').lower() in ('1', 'true', 'yes')


class OracleDB:
    def __init__(self, user=None, password=None, dsn=None, wallet=None, wallet_password=None):
        # Load primary settings from args or environment
        self.user = user or os.getenv('ORACLE_USER')
        self.password = password or os.getenv('ORACLE_PASSWORD')
        self.dsn = dsn or os.getenv('ORACLE_DSN')
        self.wallet = wallet or os.getenv('ORACLE_WALLET')
        self.wallet_password = wallet_password or os.getenv('ORACLE_WALLET_PASSWORD')

        # If wallet_password still missing, try reading project oracle-config.json
        if not self.wallet_password:
            try:
                from pathlib import Path
                import json
                root = Path(__file__).resolve().parent.parent
                cfg_path = root / 'oracle-config.json'
                if cfg_path.exists():
                    cfg = json.loads(cfg_path.read_text())
                    self.wallet_password = cfg.get('wallet_password') or self.wallet_password
                    # If dsn/credentials not provided, pick them from config as a fallback
                    self.user = self.user or cfg.get('username')
                    self.password = self.password or cfg.get('password')
                    self.dsn = self.dsn or cfg.get('connection_string')
                    if not self.wallet:
                        w = cfg.get('wallet_dir')
                        if w:
                            self.wallet = str((root / w).resolve()) if not Path(w).is_absolute() else w
            except Exception:
                logger.exception('Failed to load oracle-config.json for wallet password and fallbacks')

        # Do not import oracledb here because it may read TNS_ADMIN at import time.
        # We'll import lazily in _connect() after any wallet/TNS_ADMIN env is set.
        self._driver = None

    def _connect(self):
        if not ORACLE_ENABLED:
            logger.debug("Oracle DB integration disabled via ORACLE_DB_ENABLED")
            return None
        # Load driver lazily so TNS_ADMIN can be set before import
        if self._driver is None:
            try:
                # Ensure TNS_ADMIN is set if wallet path was provided
                if self.wallet:
                    os.environ.setdefault('TNS_ADMIN', self.wallet)
                import oracledb as _drv
                self._driver = _drv
            except Exception as e:
                logger.warning(f"oracledb driver not available: {e}")
                return None
        if not self.dsn:
            logger.warning("ORACLE_DSN not configured; cannot connect to Oracle DB")
            return None
        # Build connection kwargs
        kwargs = {}
        if self.user:
            kwargs['user'] = self.user
        if self.password:
            kwargs['password'] = self.password

        # Prefer wallet-based connection when wallet path is available. Pass
        # wallet_location and wallet_password to the driver which worked in
        # interactive tests.
        try:
            if self.wallet:
                # Ensure env TNS_ADMIN points to wallet
                os.environ.setdefault('TNS_ADMIN', self.wallet)
                # Pass wallet_location and wallet_password if available
                if self.wallet_password:
                    conn = self._driver.connect(dsn=self.dsn, wallet_location=self.wallet, wallet_password=self.wallet_password, **kwargs)
                    return conn
                else:
                    # Try connecting with wallet_location only
                    try:
                        conn = self._driver.connect(dsn=self.dsn, wallet_location=self.wallet, **kwargs)
                        return conn
                    except Exception:
                        # Fall back to plain connect below
                        logger.debug('Wallet location connect failed, falling back to non-wallet connect')

            # Fallback: plain connect using dsn/user/password
            conn = self._driver.connect(dsn=self.dsn, **kwargs)
            return conn
        except Exception as e:
            logger.warning(f"Failed to connect to Oracle DB: {e}")
            return None

    def init_db(self):
        # No special initialization required here
        return True

    def insert(self, record: Dict) -> bool:
        conn = self._connect()
        if conn is None:
            return False
        try:
            cur = conn.cursor()
            cur.execute("""
                BEGIN
                    EXECUTE IMMEDIATE 'CREATE TABLE telemetry (
                        id NUMBER GENERATED BY DEFAULT AS IDENTITY,
                        timestamp VARCHAR2(64),
                        temperature NUMBER,
                        humidity NUMBER,
                        wind_speed NUMBER,
                        wind_dir NUMBER,
                        barometer NUMBER,
                        rain_rate NUMBER,
                        solar_rad NUMBER,
                        uv NUMBER,
                        ac_solar_w NUMBER,
                        house_power_w NUMBER,
                        net_balance NUMBER
                    )';
                EXCEPTION
                    WHEN OTHERS THEN
                        IF SQLCODE != -955 THEN RAISE; END IF;
                END;
            """)

            insert_sql = ("INSERT INTO telemetry (timestamp, temperature, humidity, wind_speed, wind_dir, "
                          "barometer, rain_rate, solar_rad, uv, ac_solar_w, house_power_w, net_balance) "
                          "VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12)")

            params = [
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
            ]
            cur.execute(insert_sql, params)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Telemetry stored to Oracle DB")
            return True
        except Exception as e:
            logger.error(f"Error storing telemetry to Oracle DB: {e}")
            try:
                conn.close()
            except Exception:
                pass
            return False

    def fetch_rows(self, limit: int = 200):
        """Return last `limit` rows ordered ascending like SQLite fetch_rows."""
        try:
            conn = self._connect()
            if conn is None:
                return []
            cur = conn.cursor()
            sql = ("SELECT * FROM (SELECT * FROM telemetry ORDER BY id DESC) "
                   "WHERE ROWNUM <= :1 ORDER BY id ASC")
            cur.execute(sql, (limit,))
            cols = [c[0].lower() for c in cur.description]
            rows = []
            for r in cur.fetchall():
                rows.append({cols[i]: r[i] for i in range(len(cols))})
            cur.close()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Oracle fetch_rows failed: {e}")
            return []

    def fetch_statistics_daily(self):
        try:
            conn = self._connect()
            if conn is None:
                return []
            cur = conn.cursor()
            sql = """
                SELECT 
                    'Periodo ' || (FLOOR((id - 1) / 100) + 1) as date,
                    ROUND(SUM(ac_solar_w) / 1000.0, 2) as generated_kwh,
                    ROUND(SUM(house_power_w) / 1000.0, 2) as consumed_kwh,
                    ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 1000.0, 2) as sold_excess_kwh,
                    ROUND(AVG(ac_solar_w), 1) as avg_solar_w,
                    ROUND(AVG(house_power_w), 1) as avg_consumption_w
                FROM (
                    SELECT * FROM telemetry 
                    WHERE id > (SELECT MAX(id) - 1000 FROM telemetry)
                    ORDER BY id DESC
                )
                GROUP BY FLOOR((id - 1) / 100)
                ORDER BY FLOOR((id - 1) / 100) DESC
                FETCH FIRST 30 ROWS ONLY
            """
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Oracle fetch_statistics_daily failed: {e}")
            return []

    def fetch_statistics_monthly(self):
        try:
            conn = self._connect()
            if conn is None:
                return []
            cur = conn.cursor()
            sql = """
                SELECT 
                    'Atual' as month,
                    ROUND(SUM(ac_solar_w) / 1000.0, 2) as generated_kwh,
                    ROUND(SUM(house_power_w) / 1000.0, 2) as consumed_kwh,
                    ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 1000.0, 2) as sold_excess_kwh,
                    ROUND(AVG(ac_solar_w), 1) as avg_solar_w,
                    ROUND(AVG(house_power_w), 1) as avg_consumption_w
                FROM telemetry
            """
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Oracle fetch_statistics_monthly failed: {e}")
            return []

    def fetch_summary(self):
        try:
            conn = self._connect()
            if conn is None:
                return {'today': {'generated': 0, 'consumed': 0, 'sold': 0}, 'month': {'generated': 0, 'consumed': 0, 'sold': 0}}
            cur = conn.cursor()
            from datetime import datetime, date, timedelta
            hoje_inicio = datetime.now().strftime('%Y-%m-%d 00:00:00')
            hoje_fim = datetime.now().strftime('%Y-%m-%d 23:59:59')

            cur.execute("""
                SELECT 
                    ROUND(SUM(ac_solar_w) / 360000.0, 2) as generated_kwh_today,
                    ROUND(SUM(house_power_w) / 360000.0, 2) as consumed_kwh_today,
                    ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 360000.0, 2) as sold_kwh_today
                FROM telemetry
                WHERE timestamp >= :1 AND timestamp <= :2
            """, (hoje_inicio, hoje_fim))
            day_row = cur.fetchone()

            mes_inicio = datetime.now().strftime('%Y-%m-01 00:00:00')
            hoje = date.today()
            proximo_mes = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m-%d 00:00:00')

            cur.execute("""
                SELECT 
                    ROUND(SUM(ac_solar_w) / 360000.0, 2) as generated_kwh_month,
                    ROUND(SUM(house_power_w) / 360000.0, 2) as consumed_kwh_month,
                    ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 360000.0, 2) as sold_kwh_month
                FROM telemetry
                WHERE timestamp >= :1 AND timestamp < :2
            """, (mes_inicio, proximo_mes))
            month_row = cur.fetchone()
            cur.close()
            conn.close()

            return {
                'today': {
                    'generated': (day_row[0] if day_row and day_row[0] is not None else 0),
                    'consumed': (day_row[1] if day_row and day_row[1] is not None else 0),
                    'sold': (day_row[2] if day_row and day_row[2] is not None else 0)
                },
                'month': {
                    'generated': (month_row[0] if month_row and month_row[0] is not None else 0),
                    'consumed': (month_row[1] if month_row and month_row[1] is not None else 0),
                    'sold': (month_row[2] if month_row and month_row[2] is not None else 0)
                }
            }
        except Exception as e:
            logger.error(f"Oracle fetch_summary failed: {e}")
            return {'today': {'generated': 0, 'consumed': 0, 'sold': 0}, 'month': {'generated': 0, 'consumed': 0, 'sold': 0}}
