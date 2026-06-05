"""
Database Module - Gerenciamento da conexão SQLite
"""
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Lê o caminho da BD a partir de variável de ambiente (ou usa padrão local)
DB_PATH = os.getenv('DB_PATH', 'telemetry.db')


def get_db_connection():
    """
    Retorna uma conexão com a BD SQLite
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Inicializa a base de dados SQLite e cria a tabela se não existir
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
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
            logger.info(f"Base de dados inicializada em: {DB_PATH}")
    except Exception as e:
        logger.error(f"Erro ao inicializar BD: {str(e)}")
        raise
