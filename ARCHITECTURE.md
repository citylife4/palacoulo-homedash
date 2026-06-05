# 🏗️ ARQUITETURA - EcoPi OS v2.7

## Visão Geral da Refatoração

O aplicativo original monolítico (`weather_app.py` de 404 linhas) foi transformado numa arquitetura profissional, modular e containerizada seguindo as melhores práticas de engenharia de software.

## 📊 Estrutura de Diretórios

```
auto-energy/
│
├── 📁 src/                          # Core da aplicação
│   ├── __init__.py                  # Application Factory
│   ├── database.py                  # Módulo de Base de Dados
│   ├── shelly_service.py            # Integração Shelly (HTTP)
│   ├── routes.py                    # Definição de Rotas (Blueprints)
│   └── 📁 templates/
│       └── dashboard.html           # Interface Web (HTML/CSS/JS)
│
├── run.py                           # Entry Point
├── requirements.txt                 # Dependências Python
├── Dockerfile                       # Docker Configuration
├── docker-compose.yml               # Docker Compose Orchestration
├── .dockerignore                    # Files ignored by Docker
├── .gitignore                       # Git ignore patterns
├── README.md                        # Documentação Principal
├── DEPLOYMENT.md                    # Guia de Deployment
└── ARCHITECTURE.md                  # Este arquivo
```

---

## 🔄 Fluxo de Dados

### 1️⃣ Inicialização (Startup)

```
run.py
  ↓
create_app() [src/__init__.py]
  ├→ init_db() [src/database.py]
  │   └→ CREATE TABLE telemetry (if not exists)
  └→ register_blueprints(app)
      └→ Registar rotas GET /, POST /weather, GET /api/live
```

### 2️⃣ Receção de Dados Meteorológicos

```
POST /weather (Weather Station)
  ↓
handle_weather_webhook() [src/routes.py]
  ├→ Parse Form Data
  ├→ Conversão de Métricas (°F→°C, mph→km/h, etc)
  ├→ fetch_shelly_solar() [src/shelly_service.py]
  ├→ fetch_shelly_house() [src/shelly_service.py]
  ├→ Calcular net_balance = ac_solar - house_power
  └→ INSERT INTO telemetry [src/database.py]
```

### 3️⃣ Polling do Dashboard (A cada 3s)

```
Dashboard JavaScript
  ↓
GET /api/live [fetch() - 3 segundos]
  ↓
get_live_data() [src/routes.py]
  ├→ SELECT * FROM telemetry (últimos 30)
  ├→ Formatar histórico para gráficos
  └→ Return JSON {latest, history}
  ↓
updateDashboard() [dashboard.html]
  ├→ Atualizar cards com últimas leituras
  ├→ Formatar potência (W ↔ kW)
  ├→ Atualizar gráficos em tempo real
  └→ Renderizar status do balanço energético
```

---

## 🏛️ Arquitetura de Camadas

```
┌─────────────────────────────────────────────┐
│   PRESENTATION LAYER (Frontend)             │
│   - dashboard.html (HTML/CSS/JS)            │
│   - Chart.js (Gráficos)                     │
│   - Tailwind CSS (Styling)                  │
└────────────────────┬────────────────────────┘
                     │ HTTP/JSON
┌────────────────────▼────────────────────────┐
│   API LAYER (Routes - Blueprints)           │
│   - GET  / → index()                        │
│   - POST /weather → handle_weather_webhook()│
│   - GET  /api/live → get_live_data()       │
└────────────────────┬────────────────────────┘
                     │ Python Functions
┌────────────────────▼────────────────────────┐
│   SERVICE LAYER (Business Logic)            │
│   - shelly_service.py                       │
│     • fetch_shelly_solar()                  │
│     • fetch_shelly_house()                  │
│   - Conversões de métricas                  │
│   - Cálculos (net_balance, etc)             │
└────────────────────┬────────────────────────┘
                     │ SQL/Database
┌────────────────────▼────────────────────────┐
│   DATA LAYER (Database)                     │
│   - database.py                             │
│   - SQLite (telemetry.db)                   │
│   - 13 colunas, índices otimizados          │
└─────────────────────────────────────────────┘
```

---

## 📦 Componentes Detalhados

### 1. Application Factory (`src/__init__.py`)

**Responsabilidade**: Inicialização centralizada da aplicação

```python
def create_app():
    app = Flask(__name__, template_folder='templates')
    init_db()                      # Preparar BD
    register_blueprints(app)       # Registar rotas
    return app
```

**Benefícios**:
- ✅ Fácil de testar (criar múltiplas instâncias)
- ✅ Configuração centralizada
- ✅ Escalável para múltiplos ambientes

---

### 2. Database Module (`src/database.py`)

**Responsabilidade**: Abstração da camada de dados

```python
# Lê do ambiente
DB_PATH = os.getenv('DB_PATH', 'telemetry.db')

# Conexões seguras
def get_db_connection():
    return sqlite3.connect(DB_PATH)

# Inicialização
def init_db():
    CREATE TABLE IF NOT EXISTS telemetry (...)
```

**Benefícios**:
- ✅ Centralizado (fácil migrar BD se necessário)
- ✅ Variáveis de ambiente (configuração flexível)
- ✅ Row factory (acesso por coluna ou índice)
- ✅ Timeout configurável

**Schema**:
| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | INTEGER | Primary Key |
| timestamp | TEXT | HH:MM:SS |
| temperature | REAL | °C |
| humidity | INTEGER | % |
| wind_speed | REAL | km/h |
| wind_dir | INTEGER | 0-360° |
| barometer | REAL | hPa |
| rain_rate | REAL | mm/h |
| solar_rad | INTEGER | W/m² |
| uv | INTEGER | Índice UV |
| ac_solar_w | REAL | Watts |
| house_power_w | REAL | Watts |
| net_balance | REAL | Watts |

---

### 3. Shelly Service (`src/shelly_service.py`)

**Responsabilidade**: Integração com dispositivos Shelly (isolado)

```python
SHELLY_SOLAR_IP = os.getenv('SHELLY_SOLAR_IP')
SHELLY_HOUSE_IP = os.getenv('SHELLY_HOUSE_IP')

def fetch_shelly_solar():
    # Gen2: /rpc/Shelly.GetStatus
    # Gen1: /status
    return power_in_watts

def fetch_shelly_house():
    # Soma de todos os circuitos
    return total_power_in_watts
```

**Benefícios**:
- ✅ Isolado (fácil testar/mockar)
- ✅ Compatível Gen1 e Gen2
- ✅ Timeout proteção
- ✅ Fallback para 0.0W se erro

---

### 4. Routes Module (`src/routes.py`)

**Responsabilidade**: Definição de endpoints REST

#### Rota 1: GET /
```python
@main_bp.route('/', methods=['GET'])
def index():
    return render_template('dashboard.html')
```
- Serve interface web

#### Rota 2: POST /weather
```python
@main_bp.route('/weather', methods=['POST'])
def handle_weather_webhook():
    # Recebe dados da estação meteorológica
    # Converte métricas
    # Busca dados Shelly (paralelo)
    # Guarda na BD
```
- Webhook da estação meteorológica
- Lógica crítica de negócio

#### Rota 3: GET /api/live
```python
@main_bp.route('/api/live', methods=['GET'])
def get_live_data():
    # Retorna últimos 30 registos (histórico)
    # Retorna último registo (realtime)
```
- API JSON para frontend
- Polling a cada 3 segundos

**Benefícios**:
- ✅ Blueprints (escalável para múltiplos módulos)
- ✅ Separação clara de responsabilidades
- ✅ Logging centralizado
- ✅ Error handling robusto

---

### 5. Frontend Template (`src/templates/dashboard.html`)

**Responsabilidade**: Interface web

**Tecnologias**:
- **Tailwind CSS**: Styling responsivo
- **Chart.js**: Gráficos em tempo real
- **Vanilla JavaScript**: Polling (fetch API)

**Funcionalidades**:
1. **Polling**: `setInterval(updateDashboard, 3000)`
2. **Smart Power Formatting**:
   ```javascript
   if (absValue >= 1000) {
       return { value: (value/1000).toFixed(2), unit: 'kW' };
   }
   return { value: value.toFixed(1), unit: 'W' };
   ```
3. **Gráficos em Tempo Real**: 
   - Temperatura (histórico)
   - Energia (solar, consumo, radiação)
4. **Status Dinâmico**: Verde (excedente) / Laranja (importação)

**Preservação de Português**:
- ✅ Todas as labels em português
- ✅ Legendas de gráficos em português
- ✅ Mensagens de status em português

---

## 🐳 Docker & Containerização

### Dockerfile (python:3.11-slim)

```dockerfile
# Base: python:3.11-slim (89MB vs 340MB full)

# Layer 1: System dependencies
RUN apt-get install gcc

# Layer 2: Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 3: Application code
COPY . .

# Layer 4: Metadata
EXPOSE 8000
CMD ["python", "run.py"]
```

**Otimizações**:
- ✅ Multi-stage implicit (separação clara)
- ✅ Cache layer para pip install
- ✅ Minimal base image
- ✅ No cache pip (reduz tamanho final)

### Docker Compose

```yaml
services:
  ecopi-dashboard:
    build: .
    restart: always
    ports:
      - "8000:8000"
    environment:
      DB_PATH: /data/telemetry.db
      SHELLY_SOLAR_IP: "192.168.188.25"
      SHELLY_HOUSE_IP: "192.168.188.5"
      TZ: "Europe/Lisbon"
    volumes:
      - ecopi_data:/data
    networks:
      - ecopi_network
```

**Benefícios**:
- ✅ Configuração declarativa
- ✅ Volume persistente para BD
- ✅ Restart automático
- ✅ Network isolada
- ✅ Fácil scale-up

---

## 📊 Fluxo de Dados Completo

```
1. WEATHER STATION                  [Externa]
   ├─ Dados meteorológicos
   └─ POST http://raspberry:8000/weather
      
2. WEBHOOK HANDLER                  [src/routes.py]
   ├─ Parse form data
   ├─ Conversão de métricas
   └─ Fetch Shelly devices (paralelo)
      
3. SHELLY INTEGRATION               [src/shelly_service.py]
   ├─ HTTP GET to SHELLY_SOLAR_IP
   ├─ HTTP GET to SHELLY_HOUSE_IP
   └─ Return power in Watts
      
4. DATABASE PERSISTENCE             [src/database.py]
   └─ INSERT INTO telemetry (...)
      
5. FRONTEND POLLING                 [dashboard.html]
   ├─ setInterval(..., 3000)
   ├─ GET /api/live
   └─ JSON {latest, history}
      
6. REAL-TIME RENDERING              [JavaScript]
   ├─ Update cards (latest values)
   ├─ Format power (W ↔ kW)
   ├─ Update charts (history)
   └─ Dynamic status (green/orange)
```

---

## 🔐 Segurança

### Implementado
- ✅ Environment variables para IPs/portas
- ✅ SQL com parametrização (previne injeção)
- ✅ Try-catch para HTTP requests
- ✅ Timeout proteção (1.5s)
- ✅ Logging de erros

### Recomendado (Production)
- 🔲 HTTPS/TLS (Nginx reverse proxy)
- 🔲 Autenticação (JWT/OAuth)
- 🔲 Rate limiting
- 🔲 CORS configurado
- 🔲 Input validation (Marshmallow)

---

## 📈 Performance

### Otimizações Implementadas
- ✅ DB Row factory (access by name)
- ✅ SELECT LIMIT 30 (não sobrecarrega)
- ✅ Chart update sem redraw completo
- ✅ HTTP timeout (1.5s)
- ✅ No cache pip (reduz imagem Docker)

### Possíveis Melhorias
- 🔲 Índices na BD (timestamp, id)
- 🔲 Caching com Redis
- 🔲 Compressão gzip
- 🔲 CDN para státicos (Tailwind, Chart.js)
- 🔲 WebSocket para real-time (vs polling)

---

## 🧪 Testabilidade

```
✅ Application Factory (fácil de testar)
✅ Blueprints (testes isolados por rota)
✅ Database abstraction (pode mockar)
✅ Shelly service isolado (pode mockar)
✅ Template em arquivo (não hardcoded)

Testes possíveis:
- Test factory creation
- Test database initialization
- Test API endpoints
- Test conversions
- Test error handling
```

---

## 🚀 Deployment

### Local Development
```bash
pip install -r requirements.txt
python run.py
```

### Docker (Single Container)
```bash
docker build -t ecopi .
docker run -p 8000:8000 ecopi
```

### Docker Compose (Recommended)
```bash
docker-compose up -d
```

### Production (Kubernetes)
- Image: `ecopi-dashboard:latest`
- Port: 8000
- Volume mount: `/data` (BD persistente)
- Env vars: `DB_PATH`, `SHELLY_*_IP`

---

## 📊 Comparação Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Arquivos** | 1 (404 linhas) | 8+ (modular) |
| **HTML** | String Python | Template .html |
| **BD** | Hardcoded `telemetry.db` | `DB_PATH` env var |
| **Shelly IPs** | Hardcoded | Env vars |
| **Escalabilidade** | Baixa | Alta |
| **Testabilidade** | Difícil | Fácil |
| **Containerização** | Não | Sim (Docker) |
| **CI/CD Ready** | Não | Sim |
| **Logging** | Apenas print() | Logging module |
| **Error Handling** | Básico | Robusto |

---

## 🔧 Manutenção Futura

### Adicionar Nova Feature

1. **Criar novo blueprint** (ex: alerts)
   ```python
   alerts_bp = Blueprint('alerts', __name__)
   # ... rotas
   ```

2. **Registar em `register_blueprints()`**
   ```python
   app.register_blueprint(alerts_bp)
   ```

3. **Template corresponde** (ex: alerts.html)

4. **Testar isoladamente**

5. **Fazer commit & deploy**

### Migrações de BD

Usar Alembic/Migrate (futura):
```bash
flask db migrate
flask db upgrade
```

### Versionamento de API

Suportar múltiplas versões:
```python
api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')
api_v2_bp = Blueprint('api_v2', __name__, url_prefix='/api/v2')
```

---

## 📚 Referências de Design

- **Design Pattern**: Application Factory (Flask)
- **Architectural Style**: Layered (N-Tier)
- **API Design**: REST
- **Database**: SQLite (relational)
- **Frontend**: SPA (Single Page App)
- **Containerization**: Docker & Compose

---

## 🎓 Aprendizados & Best Practices

1. **Separação de Responsabilidades**: Cada módulo tem uma única responsabilidade
2. **DRY (Don't Repeat Yourself)**: Código modular, reutilizável
3. **KISS (Keep It Simple, Stupid)**: Solução simples, não over-engineered
4. **Environment Configuration**: Tudo configurável via variáveis
5. **Error Handling**: Try-catch, logging, fallbacks
6. **Testing**: Código facilmente testável
7. **Documentation**: README, DEPLOYMENT, ARCHITECTURE

---

**Versão**: 2.7  
**Refatorado em**: Junho 2026  
**Status**: ✅ Production Ready
