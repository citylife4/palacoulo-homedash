import os
import math
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# -------------------------------------------------------------------------
# CONFIGURAÇÕES E BANCO DE DADOS
# -------------------------------------------------------------------------
DB_FILE = "telemetry.db"
SHELLY_SOLAR_IP = "192.168.188.25"
SHELLY_HOUSE_IP = "192.168.188.5"
TIMEOUT_HTTP = 1.5

def init_db():
    """Inicializa a base de dados SQLite e cria a tabela se não existir"""
    with sqlite3.connect(DB_FILE) as conn:
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

# Inicializa imediatamente ao arrancar o script
init_db()

# -------------------------------------------------------------------------
# FUNÇÕES AUXILIARES DE INTEGRAÇÃO (SHELLY API)
# -------------------------------------------------------------------------
def fetch_shelly_solar():
    try:
        url = f"http://{SHELLY_SOLAR_IP}/rpc/Shelly.GetStatus"
        res = requests.get(url, timeout=TIMEOUT_HTTP)
        if res.status_code == 200:
            data = res.json()
            if 'pm1:0' in data and 'apower' in data['pm1:0']:
                return float(data['pm1:0']['apower'])
            if 'switch:0' in data and 'apower' in data['switch:0']:
                return float(data['switch:0']['apower'])
    except Exception:
        pass

    try:
        url = f"http://{SHELLY_SOLAR_IP}/status"
        res = requests.get(url, timeout=TIMEOUT_HTTP)
        if res.status_code == 200:
            data = res.json()
            if 'meters' in data and len(data['meters']) > 0:
                return float(data['meters'][0]['power'])
    except Exception:
        pass
    return 0.0

def fetch_shelly_house():
    try:
        url = f"http://{SHELLY_HOUSE_IP}/status"
        res = requests.get(url, timeout=TIMEOUT_HTTP)
        if res.status_code == 200:
            data = res.json()
            if 'emeters' in data:
                return float(sum(float(m.get('power', 0.0)) for m in data['emeters']))
    except Exception:
        pass
    return 0.0

# -------------------------------------------------------------------------
# ROTAS FLASK
# -------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    """Rota que serve a Interface Web (Dashboard)"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/weather', methods=['POST'])
def handle_weather_webhook():
    """NOVA ROTA: Captura os dados enviados pela Estação Meteorológica"""
    form = request.form
    print(f"[{datetime.now().strftime('%H:%M:%S')}] -> Dados recebidos na rota /weather!")
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
        
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Integração paralela com os Shelly locais
        ac_solar = fetch_shelly_solar()
        house_power = fetch_shelly_house()
        net_balance = round(ac_solar - house_power, 1)
        
        # Gravação segura na DB
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telemetry 
                (timestamp, temperature, humidity, wind_speed, wind_dir, barometer, rain_rate, solar_rad, uv, ac_solar_w, house_power_w, net_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (current_time, temp_c, humidity, wind_kmh, wind_dir, barom_hpa, rain_mm, solar_rad, uv, round(ac_solar, 1), round(house_power, 1), net_balance))
            conn.commit()
            
        print("--> Sucesso: Dados convertidos e guardados na DB local!")
        return "Dados recebidos e processados com sucesso.", 200

    except Exception as e:
        print(f"--> ERRO ao processar os dados da rota /weather: {str(e)}")
        return f"Erro interno: {str(e)}", 400


@app.route('/api/live', methods=['GET'])
def get_live_data():
    """Endpoint API que o Dashboard consulta via JavaScript a cada 3s"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Buscar histórico (últimos 30 registos ordenados cronologicamente)
            cursor.execute("""
                SELECT * FROM (
                    SELECT * FROM telemetry ORDER BY id DESC LIMIT 30
                ) ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            
            if not rows:
                return jsonify({
                    "latest": {"timestamp": "A aguardar primeiro sinal em /weather...", "temperature": 0, "humidity": 0, "wind_speed": 0, "wind_dir": 0, "barometer": 0, "rain_rate": 0, "solar_rad": 0, "uv": 0, "ac_solar_w": 0, "house_power_w": 0, "net_balance": 0},
                    "history": {"timestamps": [], "temperature": [], "solar_rad": [], "ac_solar_w": [], "house_power_w": []}
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
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------------
# TEMPLATE HTML (DESIGN PREMIUM DARK COM POLLING REAL-TIME)
# -------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-PT" class="h-full bg-[#070a13]">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Core Dashboard - Automação Residencial</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .glass-card {
            background: rgba(15, 23, 42, 0.45);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .glow-green { box-shadow: 0 0 20px rgba(16, 185, 129, 0.1); }
        .glow-red { box-shadow: 0 0 20px rgba(239, 68, 68, 0.1); }
        .glow-blue { box-shadow: 0 0 20px rgba(59, 130, 246, 0.1); }
    </style>
</head>
<body class="text-slate-100 min-h-full flex flex-col justify-between">

    <header class="glass-card sticky top-0 z-50 border-b border-slate-800/60 px-6 py-4">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <div class="flex items-center gap-3">
                <div class="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></div>
                <h1 class="text-xl font-bold tracking-wider uppercase text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-blue-500">
                    EcoPi OS <span class="text-xs font-light text-slate-400 font-mono">v2.7 DB</span>
                </h1>
            </div>
            <div class="text-right">
                <p class="text-xs text-slate-400 uppercase tracking-widest">Último Sinal DB</p>
                <p id="live-clock" class="text-sm font-semibold font-mono text-cyan-400">A escutar em /weather...</p>
            </div>
        </div>
    </header>

    <main class="max-w-7xl w-full mx-auto p-4 md:p-6 lg:p-8 flex-grow space-y-8">
        
        <section>
            <h2 class="text-xs uppercase font-bold tracking-widest text-slate-400 mb-4 flex items-center gap-2">
                <span>⚡</span> Matriz Energética Residencial
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="glass-card rounded-2xl p-6 glow-green relative overflow-hidden">
                    <div class="absolute top-0 left-0 h-1 w-full bg-emerald-500"></div>
                    <p class="text-sm font-medium text-slate-400 uppercase">Produção Solar AC</p>
                    <div class="mt-4 flex items-baseline justify-between">
                        <span id="txt-solar" class="text-4xl font-extrabold text-emerald-400 font-mono">0.0</span>
                        <span class="text-lg font-medium text-emerald-500/80">W</span>
                    </div>
                </div>

                <div class="glass-card rounded-2xl p-6 glow-red relative overflow-hidden">
                    <div class="absolute top-0 left-0 h-1 w-full bg-rose-500"></div>
                    <p class="text-sm font-medium text-slate-400 uppercase">Consumo Geral</p>
                    <div class="mt-4 flex items-baseline justify-between">
                        <span id="txt-house" class="text-4xl font-extrabold text-rose-400 font-mono">0.0</span>
                        <span class="text-lg font-medium text-rose-500/80">W</span>
                    </div>
                </div>

                <div id="card-balance" class="glass-card rounded-2xl p-6 relative overflow-hidden">
                    <div id="border-balance" class="absolute top-0 left-0 h-1 w-full bg-slate-500"></div>
                    <p class="text-sm font-medium text-slate-400 uppercase">Balanço Líquido</p>
                    <div class="mt-4 flex items-baseline justify-between">
                        <span id="txt-balance" class="text-4xl font-extrabold font-mono text-slate-300">0.0</span>
                        <span class="text-lg font-medium text-slate-400">W</span>
                    </div>
                    <p id="txt-status-label" class="text-xs text-slate-500 mt-2">A processar...</p>
                </div>
            </div>
        </section>

        <section>
            <h2 class="text-xs uppercase font-bold tracking-widest text-slate-400 mb-4 flex items-center gap-2">
                <span>🌤️</span> Condições Atmosféricas
            </h2>
            <div class="grid grid-cols-2 lg:grid-cols-6 gap-4">
                <div class="glass-card rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-xs text-slate-400 font-medium uppercase">Temperatura</span>
                    <span class="text-2xl font-bold font-mono text-amber-400 mt-2"><span id="meta-temp">0.0</span><span class="text-sm font-sans text-slate-400 ml-1">°C</span></span>
                </div>
                <div class="glass-card rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-xs text-slate-400 font-medium uppercase">Humidade</span>
                    <span class="text-2xl font-bold font-mono text-blue-400 mt-2"><span id="meta-hum">0</span><span class="text-sm font-sans text-slate-400 ml-1">%</span></span>
                </div>
                <div class="glass-card rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-xs text-slate-400 font-medium uppercase">Vento</span>
                    <span class="text-xl font-bold font-mono text-teal-400 mt-2 truncate"><span id="meta-wind">0.0</span><span class="text-xs font-sans text-slate-400 ml-1">km/h</span></span>
                    <span id="meta-winddir" class="text-[10px] text-slate-500 font-mono mt-1">Dir: 0°</span>
                </div>
                <div class="glass-card rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-xs text-slate-400 font-medium uppercase">Pressão</span>
                    <span class="text-xl font-bold font-mono text-purple-400 mt-2"><span id="meta-barom">0.0</span><span class="text-xs font-sans text-slate-400 ml-1">hPa</span></span>
                </div>
                <div class="glass-card rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-xs text-slate-400 font-medium uppercase">Chuva</span>
                    <span class="text-2xl font-bold font-mono text-cyan-400 mt-2"><span id="meta-rain">0.0</span><span class="text-sm font-sans text-slate-400 ml-1">mm/h</span></span>
                </div>
                <div class="glass-card rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-xs text-slate-400 font-medium uppercase">Radiação / UV</span>
                    <span class="text-xl font-bold font-mono text-yellow-400 mt-2"><span id="meta-rad">0</span><span class="text-xs font-sans text-slate-400 ml-1">W/m²</span></span>
                    <span id="meta-uv" class="text-[10px] text-amber-500 font-semibold uppercase mt-1">UV: 0</span>
                </div>
            </div>
        </section>

        <section class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="glass-card rounded-2xl p-5 glow-blue">
                <p class="text-xs uppercase font-bold tracking-widest text-slate-400 mb-4">Histórico Térmico</p>
                <div class="h-64"><canvas id="chart-temp"></canvas></div>
            </div>
            <div class="glass-card rounded-2xl p-5">
                <p class="text-xs uppercase font-bold tracking-widest text-slate-400 mb-4">Fluxo de Energia Integrado</p>
                <div class="h-64"><canvas id="chart-energy"></canvas></div>
            </div>
        </section>
    </main>

    <script>
        let chartTemp, chartEnergy;

        function initCharts() {
            const ctxTemp = document.getElementById('chart-temp').getContext('2d');
            chartTemp = new Chart(ctxTemp, {
                type: 'line',
                data: { labels: [], datasets: [{ label: 'Temp (°C)', data: [], borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.05)', borderWidth: 2, fill: true, tension: 0.4, pointRadius: 1 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: 'rgba(255,255,255,0.01)' }, ticks: { color: '#64748b', font: { size: 10 } } }, y: { grid: { color: 'rgba(255,255,255,0.01)' }, ticks: { color: '#64748b', font: { size: 10 } } } } }
            });

            const ctxEnergy = document.getElementById('chart-energy').getContext('2d');
            chartEnergy = new Chart(ctxEnergy, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        { label: 'Radiação (W/m²)', data: [], borderColor: '#eab308', borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false },
                        { label: 'Produção Solar (W)', data: [], borderColor: '#10b981', borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false },
                        { label: 'Consumo Casa (W)', data: [], borderColor: '#ef4444', borderWidth: 2, pointRadius: 0, tension: 0.2, fill: false }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } }, scales: { x: { grid: { color: 'rgba(255,255,255,0.01)' }, ticks: { color: '#64748b', font: { size: 10 } } }, y: { grid: { color: 'rgba(255,255,255,0.01)' }, ticks: { color: '#64748b', font: { size: 10 } } } } }
            });
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/live');
                if (!response.ok) return;
                const data = await response.json();
                
                if (data.error) return;

                const latest = data.latest;
                const history = data.history;

                document.getElementById('live-clock').innerText = latest.timestamp;
                document.getElementById('txt-solar').innerText = latest.ac_solar_w.toFixed(1);
                document.getElementById('txt-house').innerText = latest.house_power_w.toFixed(1);
                
                const balanceElement = document.getElementById('txt-balance');
                const cardBalance = document.getElementById('card-balance');
                const borderBalance = document.getElementById('border-balance');
                const statusLabel = document.getElementById('txt-status-label');

                balanceElement.innerText = latest.net_balance.toFixed(1);

                if (latest.net_balance >= 0) {
                    balanceElement.className = "text-4xl font-extrabold font-mono text-emerald-400";
                    cardBalance.className = "glass-card rounded-2xl p-6 glow-green relative overflow-hidden";
                    borderBalance.className = "absolute top-0 left-0 h-1 w-full bg-emerald-500";
                    statusLabel.innerText = "Excedente / Autossuficiência";
                } else {
                    balanceElement.className = "text-4xl font-extrabold font-mono text-orange-400";
                    cardBalance.className = "glass-card rounded-2xl p-6 glow-red relative overflow-hidden";
                    borderBalance.className = "absolute top-0 left-0 h-1 w-full bg-orange-500";
                    statusLabel.innerText = "A Importar da Rede Comercial";
                }

                document.getElementById('meta-temp').innerText = latest.temperature.toFixed(1);
                document.getElementById('meta-hum').innerText = latest.humidity;
                document.getElementById('meta-wind').innerText = latest.wind_speed.toFixed(1);
                document.getElementById('meta-winddir').innerText = `Dir: ${latest.wind_dir}°`;
                document.getElementById('meta-barom').innerText = latest.barometer.toFixed(1);
                document.getElementById('meta-rain').innerText = latest.rain_rate.toFixed(1);
                document.getElementById('meta-rad').innerText = latest.solar_rad;
                document.getElementById('meta-uv').innerText = `UV: ${latest.uv}`;

                if(history.timestamps && history.timestamps.length > 0) {
                    chartTemp.data.labels = history.timestamps;
                    chartTemp.data.datasets[0].data = history.temperature;
                    chartTemp.update('none');

                    chartEnergy.data.labels = history.timestamps;
                    chartEnergy.data.datasets[0].data = history.solar_rad;
                    chartEnergy.data.datasets[1].data = history.ac_solar_w;
                    chartEnergy.data.datasets[2].data = history.house_power_w;
                    chartEnergy.update('none');
                }

            } catch (error) {
                console.error("Erro no Polling:", error);
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            initCharts();
            updateDashboard();
            setInterval(updateDashboard, 3000);
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    # Modo Debug ativo para termos visibilidade total no terminal do Pi
    app.run(host='0.0.0.0', port=8000, debug=True)
