"""
Routes Module - Definição de rotas usando Flask Blueprints
"""
import sqlite3
import logging
from datetime import datetime, timedelta
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
        net_balance = fetch_shelly_house()
        house_power = round(house_power + ac_solar, 1)
        
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
                SELECT * FROM telemetry ORDER BY id DESC LIMIT 1000
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if period == 'daily':
            # Estatísticas diárias - grupo simples de 100 records = 1 "dia"
            # Como os dados não têm data real, agrupamos por sequências de IDs
            cursor.execute("""
                SELECT 
                    'Período ' || ((id - 1) / 100 + 1) as date,
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
                GROUP BY ((id - 1) / 100)
                ORDER BY ((id - 1) / 100) DESC
                LIMIT 30
            """)
            
        else:  # monthly
            # Estatísticas mensais - sem data real, usar agregação simples
            # Retorna uma única agregação de todos os dados disponíveis
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
        conn.close()
        
        stats = []
        for row in rows:
            stats.append({
                "date" if period == 'daily' else "month": row[0],
                "generated": row[1],
                "consumed": row[2],
                "sold": row[3],
                "avg_solar": row[4],
                "avg_consumption": row[5]
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Resumo do dia
        cursor.execute("""
            SELECT 
                ROUND(SUM(ac_solar_w) / 1000.0, 2) as generated_kwh_today,
                ROUND(SUM(house_power_w) / 1000.0, 2) as consumed_kwh_today,
                ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 1000.0, 2) as sold_kwh_today
            FROM telemetry
            WHERE DATE(datetime(timestamp || ' 00:00:00')) = DATE('now')
        """)
        day_row = cursor.fetchone()
        
        # Resumo do mês
        cursor.execute("""
            SELECT 
                ROUND(SUM(ac_solar_w) / 1000.0, 2) as generated_kwh_month,
                ROUND(SUM(house_power_w) / 1000.0, 2) as consumed_kwh_month,
                ROUND(SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) / 1000.0, 2) as sold_kwh_month
            FROM telemetry
            WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
        """)
        month_row = cursor.fetchone()
        conn.close()
        
        return jsonify({
            "today": {
                "generated": day_row[0] or 0,
                "consumed": day_row[1] or 0,
                "sold": day_row[2] or 0
            },
            "month": {
                "generated": month_row[0] or 0,
                "consumed": month_row[1] or 0,
                "sold": month_row[2] or 0
            }
        })
        
    except Exception as e:
        error_msg = f"Erro ao buscar resumo: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500


def register_blueprints(app):
    """
    Regista todos os blueprints na aplicação
    """
    app.register_blueprint(main_bp)
