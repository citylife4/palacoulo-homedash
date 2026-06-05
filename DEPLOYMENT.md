# Guia de Deployment - EcoPi OS

## 📋 Quick Start (Docker Compose)

### Pré-requisitos
- Docker & Docker Compose instalados
- Rede local com dispositivos Shelly configurados

### 1. Clonar / Preparar o Projeto

```bash
cd ~/seu-diretorio/auto-energy
```

### 2. Configurar Variáveis de Ambiente (Opcional)

Se os IPs Shelly forem diferentes, editar `docker-compose.yml`:

```yaml
environment:
  SHELLY_SOLAR_IP: "192.168.188.25"    # Mudar para seu IP
  SHELLY_HOUSE_IP: "192.168.188.5"     # Mudar para seu IP
  TZ: "Europe/Lisbon"                   # Mudar para seu fuso horário
```

### 3. Build e Deploy

```bash
# Build da imagem (primeira vez)
docker-compose build

# Iniciar container
docker-compose up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f
```

### 4. Aceder ao Dashboard

Abrir navegador: `http://seu-ip-raspberry:8000`

### 5. Parar o Container

```bash
docker-compose down
```

---

## 🔧 Configuração da Estação Meteorológica

Configure o webhook da estação para:

**URL:** `http://seu-ip-raspberry:8000/weather`  
**Método:** `POST`  
**Tipo:** Form Data

Campos esperados:
- `tempf` (temperatura em Fahrenheit)
- `windspeedmph` (velocidade do vento em mph)
- `baromrelin` (pressão em polegadas de mercúrio)
- `rainratein` (taxa de chuva em polegadas/hora)
- `humidity` (humidade em %)
- `solarradiation` (radiação solar em W/m²)
- `uv` (índice UV)
- `winddir` (direção do vento em graus 0-360)

---

## 🏃 Execução Local (Desenvolvimento)

### Sem Docker

```bash
# 1. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
export DB_PATH=./telemetry.db
export SHELLY_SOLAR_IP=192.168.188.25
export SHELLY_HOUSE_IP=192.168.188.5
export DEBUG=True

# 4. Executar
python run.py
```

Servidor estará em: `http://localhost:8000`

### Com Docker Localmente

```bash
docker build -t ecopi:dev .

docker run -it \
  -p 8000:8000 \
  -e DB_PATH=/data/telemetry.db \
  -e SHELLY_SOLAR_IP=192.168.188.25 \
  -e SHELLY_HOUSE_IP=192.168.188.5 \
  -v $(pwd):/app \
  ecopi:dev
```

---

## 📊 Monitoramento

### Ver Logs em Tempo Real

```bash
docker-compose logs -f ecopi-dashboard
```

### Aceder ao Volume de Dados

```bash
# Ver dados do volume
docker volume inspect ecopi_data

# Copiar dados para backup
docker cp ecopi-dashboard:/data/telemetry.db ./backup-telemetry.db
```

### Verificar Conectividade Shelly

```bash
# Dentro do container
docker exec ecopi-dashboard curl http://SHELLY_IP/status

# Ou diretamente
curl http://192.168.188.25/status
curl http://192.168.188.5/status
```

---

## 🔄 Atualizações

### Atualizar Código

```bash
# Parar container
docker-compose down

# Fazer pull do novo código
git pull

# Rebuild e start
docker-compose up -d --build
```

### Preservar Base de Dados

O volume `ecopi_data` é persistente. Para não perder dados:

```bash
# Dados são automaticamente preservados no volume
docker-compose down  # Dados mantêm-se
docker-compose up -d # Reusa volume existente
```

### Reset Completo (Perder dados!)

```bash
docker-compose down -v  # Remove volumes também
docker-compose up -d
```

---

## 🐛 Troubleshooting

### Container não inicia

```bash
docker-compose logs ecopi-dashboard

# Verificar sintaxe YAML
docker-compose config

# Rebuild
docker-compose build --no-cache
docker-compose up -d
```

### Dashboard branco / Sem dados

1. **Aguardar primeiro webhook** da estação meteorológica
2. **Verificar logs**: `docker-compose logs | grep -i erro`
3. **Verificar conectividade Shelly**:
   ```bash
   docker exec ecopi-dashboard curl http://192.168.188.25/status
   ```

### Base de dados locked / Corruption

```bash
# Backup
docker cp ecopi-dashboard:/data/telemetry.db ./telemetry.db.backup

# Restart
docker-compose restart

# Se problema persistir, remover volume
docker-compose down -v
docker-compose up -d
```

### Alto uso de CPU

- Reduzir frequência de polling no dashboard.html (mudar 3000ms para 5000ms)
- Reduzir número de gráficos mantidos em memória
- Restartar container: `docker-compose restart`

---

## 🔐 Segurança (Production)

⚠️ **IMPORTANTE**: O setup atual é para LAN privada. Para exposição pública:

### 1. Adicionar Autenticação

Modificar `src/routes.py`:

```python
from functools import wraps
from flask import request, abort

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != os.getenv('API_KEY', 'default-key'):
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/api/live', methods=['GET'])
@require_api_key
def get_live_data():
    ...
```

### 2. HTTPS/TLS

Usar Nginx reverse proxy com Let's Encrypt:

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
    depends_on:
      - ecopi-dashboard
```

### 3. Rate Limiting

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app, key_func=get_remote_address)

@main_bp.route('/api/live', methods=['GET'])
@limiter.limit("10 per minute")
def get_live_data():
    ...
```

### 4. Input Validation

```python
from marshmallow import Schema, fields, ValidationError

class WeatherSchema(Schema):
    tempf = fields.Float(required=True, validate=lambda x: -50 < x < 140)
    humidity = fields.Int(required=True, validate=lambda x: 0 <= x <= 100)
    # ... mais campos
```

---

## 📈 Performance Tuning

### Limpar Dados Antigos

Adicionar script de manutenção em `src/maintenance.py`:

```python
import sqlite3
from datetime import datetime, timedelta

def cleanup_old_data(days_keep=30):
    cutoff = datetime.now() - timedelta(days=days_keep)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM telemetry WHERE timestamp < ?", (cutoff,))
        conn.commit()
```

Agendar com cron (fora do container):

```bash
0 2 * * * docker exec ecopi-dashboard python -c "from src.maintenance import cleanup_old_data; cleanup_old_data()"
```

### Indexação de BD

Melhorar queries em `src/database.py`:

```python
cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_id ON telemetry(id)")
```

---

## 📚 Referências

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Shelly API](https://shelly.cloud/documents/developers/api)
- [SQLite Optimization](https://www.sqlite.org/queryplanner.html)

---

**Versão**: 2.7  
**Última atualização**: Junho 2026  
**Suporte**: EcoPi Home Automation System
