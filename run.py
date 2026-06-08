"""
Entry Point - Executa a aplicação Flask
"""
import os
import logging
from src import create_app

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    app = create_app()
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8001))
    debug = True
    
    print(f"🚀 Iniciando EcoPi OS em http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
