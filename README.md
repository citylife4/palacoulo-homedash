# EcoPi OS - Home Automation Dashboard

## Descrição

EcoPi OS é um Dashboard de Automação Residencial profissional, modular e containerizado, que integra dados meteorológicos, produção solar e consumo energético em tempo real.

## Arquitetura Refatorada

```
auto-energy/
├── src/
│   ├── __init__.py              # Application Factory
│   ├── database.py              # Gestão de conexão SQLite
│   ├── shelly_service.py        # Integração com dispositivos Shelly (HTTP)
│   ├── routes.py                # Definição de rotas (Blueprints)
│   └── templates/
│       └── dashboard.html       # Interface web (HTML/CSS/JavaScript)
├── run.py                       # Entry point da aplicação
├── requirements.txt             # Dependências Python
├── Dockerfile                   # Configuração Docker (otimizada)
├── docker-compose.yml           # Orquestração de containers
├── .gitignore                   # Arquivos ignorados no Git
└── README.md                    # Este arquivo
```

## Componentes Principais

### 1. Application Factory (`src/__init__.py`)
- Cria e configura a aplicação Flask usando o padrão Factory
- Inicializa a base de dados SQLite
- Regista os Blueprints (rotas)

### 2. Database Module (`src/database.py`)
- Gerencia a conexão com SQLite
- Lê o caminho da BD a partir de variável de ambiente `DB_PATH`
- Cria automaticamente a tabela `telemetry` se não existir
- Função `get_db_connection()` para conexões seguras

### 3. Shelly Service (`src/shelly_service.py`)
- Isolamento das funções HTTP para dispositivos Shelly
- `fetch_shelly_solar()`: Busca potência AC do painel solar
- `fetch_shelly_house()`: Busca consumo total da casa
- Lê IPs dos dispositivos a partir de variáveis de ambiente
- Timeout configurável (1.5 segundos)

### 4. Routes Module (`src/routes.py`)
- Define rotas usando Flask Blueprints
- **GET `/`**: Serve a interface web (dashboard)
- **POST `/weather`**: Recebe dados da estação meteorológica
  - Converte métricas (°F→°C, mph→km/h, in→mm/hPa)
  - Busca dados dos Shelly em paralelo
  - Calcula balanço líquido
  - Guarda tudo na base de dados
- **GET `/api/live`**: Retorna dados em JSON
  - Último registo (para cards em tempo real)
  - Histórico dos últimos 30 registos (para gráficos)

### 5. Frontend Template (`src/templates/dashboard.html`)
- Interface web moderna e responsiva (Tailwind CSS + Chart.js)
- Todas as labels em português (preservadas do original)
- Polling a cada 3 segundos via `/api/live`
- Formatação inteligente de potência: ≥1000W → kW, <1000W → W
- Gráficos em tempo real (temperatura, energia)
- Cards com dados atmosféricos

### 6. Entry Point (`run.py`)
- Inicializa a aplicação chamando `create_app()`
- Executa o servidor em `host=0.0.0.0:port=8000`
- Configurações lidas de variáveis de ambiente

## Variáveis de Ambiente

```bash
# Aplicação
DEBUG=False              # Modo debug (True/False)
HOST=0.0.0.0           # Host de escuta
PORT=8000              # Porta de escuta

# Base de Dados
DB_PATH=/data/telemetry.db    # Caminho para ficheiro SQLite

# Shelly Devices
SHELLY_SOLAR_IP=192.168.188.25    # IP do Shelly Solar
SHELLY_HOUSE_IP=192.168.188.5     # IP do Shelly Casa

# Sistema
TZ=Europe/Lisbon       # Fuso horário
```

## Execução

### Local (sem Docker)

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Executar aplicação
python run.py
```

A aplicação estará disponível em: `http://localhost:8000`

### Com Docker Compose

```bash
# 1. Build e start
docker-compose up -d

# 2. Ver logs
docker-compose logs -f

# 3. Parar
docker-compose down
```

A aplicação estará disponível em: `http://localhost:8000`

### Apenas Docker

```bash
# Build
docker build -t ecopi-dashboard:latest .

# Run
docker run -d \
  --name ecopi-dashboard \
  -p 8000:8000 \
  -e DB_PATH=/data/telemetry.db \
  -e SHELLY_SOLAR_IP=192.168.188.25 \
  -e SHELLY_HOUSE_IP=192.168.188.5 \
  -e TZ=Europe/Lisbon \
  -v ecopi_data:/data \
  ecopi-dashboard:latest
```

## Lógica Crítica Preservada

✅ **Rota `/weather`**: 
- Recebe dados da estação meteorológica em form data
- Converte todas as métricas (°F→°C, mph→km/h, in→mm/hPa)
- Busca dados dos Shelly em paralelo
- Calcula `net_balance = ac_solar - house_power`
- Guarda tudo na SQLite

✅ **Rota `/api/live`**:
- Retorna últimos 30 registos para gráficos
- Retorna último registo para cards em tempo real

✅ **Frontend JavaScript**:
- Polling a cada 3 segundos
- Formatação inteligente: |valor| ≥ 1000W → kW (2 casas decimais)
- Gráficos em tempo real com Chart.js

## Interface em Português

Toda a interface está em português, incluindo:
- Labels e títulos das cards
- Legendas dos gráficos
- Mensagens de status
- Variáveis de ambiente comentadas

## Optimizações Docker

- **Base image slim**: `python:3.11-slim` para reduzir tamanho
- **Cache layering**: `requirements.txt` copiado antes do código
- **No cache pip**: `--no-cache-dir` para reduzir tamanho final
- **Volume persistente**: Base de dados SQLite em volume nomeado
- **Restart policy**: `always` para recuperação automática
- **Network bridge**: Comunicação isolada

## Estrutura da Base de Dados

Tabela `telemetry`:
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
timestamp       TEXT (HH:MM:SS)
temperature     REAL (°C)
humidity        INTEGER (%)
wind_speed      REAL (km/h)
wind_dir        INTEGER (0-360°)
barometer       REAL (hPa)
rain_rate       REAL (mm/h)
solar_rad       INTEGER (W/m²)
uv              INTEGER
ac_solar_w      REAL (Watts)
house_power_w   REAL (Watts)
net_balance     REAL (Watts)
```

## Migrando do Original

Se vem do `weather_app.py` original:

1. **Copiar dados históricos** (opcional):
   ```bash
   cp telemetry.db /caminho/do/volume/docker
   ```

2. **Atualizar estação meteorológica**:
   - URL webhook: `http://seu-ip:8000/weather`
   - Método: `POST` (form data)

3. **Ajustar IPs Shelly**:
   - Editar `docker-compose.yml` ou variáveis de ambiente

## Dependências

- **Flask 3.0.0**: Web framework
- **requests 2.31.0**: HTTP client para Shelly
- **Werkzeug 3.0.1**: WSGI utility library

## Logs

Os logs estão disponíveis em:
- **Local**: stdout (console)
- **Docker**: `docker-compose logs -f ecopi-dashboard`

## Notas de Segurança

⚠️ Este é um dashboard de LAN interna. Para exposição pública:
- Adicionar autenticação (JWT/OAuth)
- Usar HTTPS/TLS
- Validar inputs rigorosamente
- Rate limiting

## Troubleshooting

### Container não inicia
```bash
docker-compose logs ecopi-dashboard
```

### Base de dados não persiste
```bash
# Verificar volume
docker volume ls
docker volume inspect ecopi_data
```

### Não consegue comunicar com Shelly
- Verificar IPs em `docker-compose.yml`
- Testar: `curl http://192.168.188.25/status`

### Gráficos vazios
- Aguardar primeiro sinal em `/weather`
- Verificar logs da estação meteorológica

---

**Versão**: 2.7  
**Desenvolvido para**: EcoPi Home Automation System  
**Licença**: Proprietária
