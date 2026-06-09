"""
Routes Module - Definição de rotas usando Flask Blueprints
"""
import logging
import datetime
from typing import Any
from flask import Blueprint, render_template, request, jsonify
from src.shelly_service import fetch_shelly_solar, fetch_shelly_house
from src.storage import get_storage

logger = logging.getLogger(__name__)

# Cria blueprint para as rotas principais
main_bp = Blueprint('main', __name__)

# Selected storage backend (sqlite or oracle)
storage: Any = get_storage()


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
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_log = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        solar = fetch_shelly_solar()
        ac_solar = 0.0 if solar < 1.0 else solar
        net_balance = fetch_shelly_house()
        house_power = round(net_balance + ac_solar, 1)
        
        # Persist using selected storage backend
        record = {
            'timestamp': current_time,
            'temperature': temp_c,
            'humidity': humidity,
            'wind_speed': wind_kmh,
            'wind_dir': wind_dir,
            'barometer': barom_hpa,
            'rain_rate': rain_mm,
            'solar_rad': solar_rad,
            'uv': uv,
            'ac_solar_w': round(ac_solar, 1),
            'house_power_w': round(house_power, 1),
            'net_balance': round(net_balance, 1)
        }

        ok = storage.insert(record)
        if not ok:
            logger.warning('Failed to persist telemetry to storage backend')
        
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
        # Fetch history from storage backend
        rows = storage.fetch_rows(limit=200)
        
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

@main_bp.route('/api/statistics', methods=['GET'])
def get_statistics():
    """
    Endpoint que retorna estatísticas diárias e mensais
    Calcula:
    - Energia gerada (produção solar)
    - Energia consumida (consumo casa)
    - Energia vendida/excedente (balanço positivo)
    """
    try:
        period = request.args.get('period', 'daily')  # 'daily' ou 'monthly'
        if period == 'daily':
            # Estatísticas diárias - grupo simples de 100 records = 1 "dia"
            # Como os dados não têm data real, agrupamos por sequências de IDs
            rows = storage.fetch_statistics_daily()
        else:
            rows = storage.fetch_statistics_monthly()
        
        stats = []
        for row in rows:
            stats.append({
                "date" if period == 'daily' else "month": row[0],
                "generated": row[1],
                "house_power": row[2],
                "sold": row[3],
                "avg_solar": row[4],
                "avg_house_power": row[5]
            })
        
        return jsonify({
            "period": period,
            "data": stats
        })
        
    except Exception as e:
        error_msg = f"Erro ao buscar estatísticas: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500


@main_bp.route('/api/summary', methods=['GET'])
def get_summary():
    """
    Endpoint que retorna resumo total do dia/mês
    """
    try:
        summary = storage.fetch_summary()
        return jsonify(summary)
        
    except Exception as e:
        error_msg = f"Erro ao buscar resumo: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500


def register_blueprints(app):
    """
    Regista todos os blueprints na aplicação
    """
    app.register_blueprint(main_bp)
