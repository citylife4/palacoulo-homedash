"""
Application Factory - Inicializa Flask, SQLite e regista Blueprints
"""
import os
from flask import Flask
from src.database import init_db
from src.routes import register_blueprints


def create_app():
    """
    Factory pattern para criar e configurar a aplicação Flask
    """
    app = Flask(__name__, template_folder='templates')
    
    # Configurações da aplicação
    app.config['JSON_SORT_KEYS'] = False
    
    # Inicializa base de dados
    init_db()
    
    # Regista as rotas (blueprints)
    register_blueprints(app)
    
    return app
