"""
Application Factory - Inicializa Flask, SQLite e regista Blueprints
"""
import os
from flask import Flask
from src.routes import register_blueprints
from src.storage import get_storage


def create_app():
    """
    Factory pattern para criar e configurar a aplicação Flask
    """
    app = Flask(__name__, template_folder='templates')
    
    # Configurações da aplicação
    app.config['JSON_SORT_KEYS'] = False
    
    # Inicializa base de dados (selected storage backend)
    storage = get_storage()
    try:
        storage.init_db()
    except Exception:
        # If backend lacks init_db or fails, continue
        pass
    
    # Regista as rotas (blueprints)
    register_blueprints(app)
    
    return app
