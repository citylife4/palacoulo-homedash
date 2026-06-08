"""
Storage selector for telemetry. Exposes a singleton `get_storage()` which
returns an object with `init_db()` and `insert(record)` and read helpers.

Use environment variable `STORAGE` set to `sqlite` (default) or `oracle`.
"""
import os
import logging

logger = logging.getLogger(__name__)

STORAGE = os.getenv('STORAGE', 'oracle').lower()

_instance = None


def get_storage():
    global _instance
    if _instance is not None:
        return _instance

    if STORAGE == 'oracle':
        from .oracle_db import OracleDB
        # Prefer configuration from oracle-config.json in project root when present
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        cfg_path = root / 'oracle-config.json'
        cfg = {}
        if cfg_path.exists():
            try:
                with cfg_path.open() as f:
                    cfg = json.load(f)
            except Exception:
                logger.exception('Failed to load oracle-config.json')

        user = cfg.get('username') or os.getenv('ORACLE_USER')
        password = cfg.get('password') or os.getenv('ORACLE_PASSWORD')
        dsn = cfg.get('connection_string') or os.getenv('ORACLE_DSN')
        wallet = cfg.get('wallet_dir') or os.getenv('ORACLE_WALLET')

        # Normalize wallet path to absolute if provided in config
        if wallet:
            wallet = str((root / wallet).resolve()) if not Path(wallet).is_absolute() else wallet

        # Export env vars for other modules that may rely on them
        if user and not os.getenv('ORACLE_USER'):
            os.environ['ORACLE_USER'] = user
        if password and not os.getenv('ORACLE_PASSWORD'):
            os.environ['ORACLE_PASSWORD'] = password
        if dsn and not os.getenv('ORACLE_DSN'):
            os.environ['ORACLE_DSN'] = dsn
        if wallet and not os.getenv('ORACLE_WALLET'):
            os.environ['ORACLE_WALLET'] = wallet

        _instance = OracleDB(user=user, password=password, dsn=dsn, wallet=wallet)
        logger.info('Storage backend: OracleDB')
    else:
        from .sqlite_db import SQLiteDB
        _instance = SQLiteDB()
        logger.info('Storage backend: SQLiteDB')

    return _instance
