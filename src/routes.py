"""
Routes Module - Definição de rotas usando Flask Blueprints
"""
import sqlite3
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from src.database import get_db_connection
from src.shelly_service import fetch_shelly_solar, fetch_shelly_house

logger = logging.getLogger(__name__)

# Cria blueprint para as rotas principais
main_bp = Blueprint('main', __name__)


@main_bp.route('/', methods=['GET'])
def index():
    """
    Rota que serve a Interface Web (Dashboard)
    """
    return render_template('dashboard.html')


@main_bp.route('/weather', methods=['POST'])
def handle_weather_webhook():
    """
    Rota que captura dados da Estação Meteorológica
    Processa conversões métricas, busca dados dos Shelly e guarda na BD
    """
    form = request.form
    current_time = datetime.now().strftime("%H:%M:%S")
    timestamp_log = datetime.now().strftime("%H:%M:%S")
    
    print(f"[{timestamp_log}] -> Dados recebidos na rota /weather!")
    print("Payload bruto enviado pela estação:", dict(form))
    
    try:
        # Conversões métricas dos dados recebidos
        temp_f = float(form.get('tempf', 32))
        temp_c = round((temp_f - 32) * 5 / 9, 1)
        
        wind_mph = float(form.get('windspeedmph', 0))
        wind_kmh = round(wind_mph * 1.60934, 1)
        
        barom_in = float(form.get('baromrelin', 29.92))
        barom_hpa = round(barom_in * 33.8639, 1)
        
        rain_in = float(form.get('rainratein', 0))
        rain_mm = round(rain_in * 25.4, 1)
        
        humidity = int(form.get('humidity', 0))
        solar_rad = int(float(form.get('solarradiation', 0)))
        uv = int(form.get('uv', 0))
        wind_dir = int(form.get('winddir', 0))
        
        # Integração paralela com os Shelly locais
        ac_solar = fetch_shelly_solar()
        house_power = fetch_shelly_house()
        net_balance = round(ac_solar - house_power, 1)
        
        # Gravação segura na DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO telemetry 
            (timestamp, temperature, humidity, wind_speed, wind_dir, barometer, rain_rate, solar_rad, uv, ac_solar_w, house_power_w, net_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (current_time, temp_c, humidity, wind_kmh, wind_dir, barom_hpa, rain_mm, solar_rad, uv, round(ac_solar, 1), round(house_power, 1), net_balance))
        conn.commit()
        conn.close()
        
        print("--> Sucesso: Dados convertidos e guardados na DB local!")
        logger.info(f"Dados de telemetria guardados com sucesso em {current_time}")
        return "Dados recebidos e processados com sucesso.", 200

    except Exception as e:
        error_msg = f"Erro ao processar os dados da rota /weather: {str(e)}"
        print(f"--> {error_msg}")
        logger.error(error_msg)
        return f"Erro interno: {str(e)}", 400


@main_bp.route('/api/live', methods=['GET'])
def get_live_data():
    """
    Endpoint API que o Dashboard consulta via JavaScript a cada 3s
    Retorna o último registo e o histórico dos últimos 30 registos
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar histórico (últimos 30 registos ordenados cronologicamente)
        cursor.execute("""
            SELECT * FROM (
                SELECT * FROM telemetry ORDER BY id DESC LIMIT 30
            ) ORDER BY id ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return jsonify({
                "latest": {
                    "timestamp": "A aguardar primeiro sinal em /weather...",
                    "temperature": 0,
                    "humidity": 0,
                    "wind_speed": 0,
                    "wind_dir": 0,
                    "barometer": 0,
                    "rain_rate": 0,
                    "solar_rad": 0,
                    "uv": 0,
                    "ac_solar_w": 0,
                    "house_power_w": 0,
                    "net_balance": 0
                },
                "history": {
                    "timestamps": [],
                    "temperature": [],
                    "solar_rad": [],
                    "ac_solar_w": [],
                    "house_power_w": []
                }
            })
        
        history = {
            "timestamps": [r["timestamp"] for r in rows],
            "temperature": [r["temperature"] for r in rows],
            "solar_rad": [r["solar_rad"] for r in rows],
            "ac_solar_w": [r["ac_solar_w"] for r in rows],
            "house_power_w": [r["house_power_w"] for r in rows]
        }
        
        latest = dict(rows[-1])
        return jsonify({"latest": latest, "history": history})
        
    except Exception as e:
        error_msg = f"Erro ao buscar dados de telemetria: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500


def register_blueprints(app):
    """
    Regista todos os blueprints na aplicação
    """
    app.register_blueprint(main_bp)
