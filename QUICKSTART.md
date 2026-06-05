# 🚀 QUICK START GUIDE - EcoPi OS v2.7

## 30-Second Setup

```bash
# Start application with Docker Compose
docker-compose up -d

# Access dashboard
# Open: http://your-raspberry-ip:8000
```

---

## File Reference Guide

### 🔹 Core Application (src/)

| File | Purpose | Key Components |
|------|---------|-----------------|
| `__init__.py` | Application Factory | `create_app()` - initializes Flask app |
| `database.py` | Data Layer | `init_db()`, `get_db_connection()` |
| `shelly_service.py` | External Integration | `fetch_shelly_solar()`, `fetch_shelly_house()` |
| `routes.py` | API Layer | `GET /`, `POST /weather`, `GET /api/live` |
| `templates/dashboard.html` | Frontend | Charts, cards, polling logic |

### 🔹 Configuration Files (Root)

| File | Purpose |
|------|---------|
| `run.py` | Entry point - runs the app |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Docker build recipe |
| `docker-compose.yml` | Container orchestration |
| `.gitignore` | Git exclusions |
| `.dockerignore` | Docker build exclusions |

### 🔹 Documentation

| File | Content |
|------|---------|
| `README.md` | Main documentation |
| `DEPLOYMENT.md` | Production deployment guide |
| `ARCHITECTURE.md` | Technical architecture details |
| `QUICKSTART.md` | This file |

---

## Environment Variables

```bash
# Database
DB_PATH=/data/telemetry.db

# Shelly Devices
SHELLY_SOLAR_IP=192.168.188.25
SHELLY_HOUSE_IP=192.168.188.5

# Application
DEBUG=False
HOST=0.0.0.0
PORT=8000

# System
TZ=Europe/Lisbon
```

---

## API Endpoints

### GET / 
- **Purpose**: Serve dashboard HTML
- **Response**: HTML page
- **Example**: `curl http://localhost:8000/`

### POST /weather
- **Purpose**: Receive data from weather station
- **Body**: Form data with weather metrics
- **Example**:
```bash
curl -X POST http://localhost:8000/weather \
  -d "tempf=72&humidity=65&windspeedmph=10.5"
```

### GET /api/live
- **Purpose**: Get current and historical telemetry
- **Response**: JSON with latest and history
- **Example**: `curl http://localhost:8000/api/live`

---

## Database Schema

```sql
Table: telemetry
├── id (INTEGER) - Primary key
├── timestamp (TEXT) - HH:MM:SS
├── temperature (REAL) - °C
├── humidity (INTEGER) - %
├── wind_speed (REAL) - km/h
├── wind_dir (INTEGER) - 0-360°
├── barometer (REAL) - hPa
├── rain_rate (REAL) - mm/h
├── solar_rad (INTEGER) - W/m²
├── uv (INTEGER) - Index
├── ac_solar_w (REAL) - Watts
├── house_power_w (REAL) - Watts
└── net_balance (REAL) - Watts (solar - house)
```

---

## Troubleshooting

### Container won't start
```bash
docker-compose logs ecopi-dashboard
docker-compose build --no-cache
```

### No data appearing
1. Wait for first webhook from weather station
2. Check Shelly devices are online:
   ```bash
   curl http://192.168.188.25/status
   curl http://192.168.188.5/status
   ```

### Need to backup database
```bash
docker cp ecopi-dashboard:/data/telemetry.db ./backup.db
```

### Need to check environment variables
```bash
docker-compose config | grep -A 10 environment
```

---

## Common Commands

```bash
# Start application
docker-compose up -d

# Stop application
docker-compose down

# View logs
docker-compose logs -f

# Restart service
docker-compose restart ecopi-dashboard

# Build fresh image
docker-compose build --no-cache

# Exec command in container
docker exec ecopi-dashboard python -c "..."

# Access database directly
docker exec ecopi-dashboard sqlite3 /data/telemetry.db

# Clear database
docker-compose down -v
docker-compose up -d
```

---

## Integration Steps

### 1. Weather Station Setup
- Configure webhook: `http://your-ip:8000/weather`
- Method: POST
- Type: Form data
- Fields: `tempf`, `humidity`, `windspeedmph`, `baromrelin`, `rainratein`, `solarradiation`, `uv`, `winddir`

### 2. Shelly Devices
- Solar inverter: IP in `SHELLY_SOLAR_IP`
- House meter: IP in `SHELLY_HOUSE_IP`
- Both must be reachable from container

### 3. Access Dashboard
- Open: `http://your-ip:8000`
- Charts update every 3 seconds
- Shows real-time energy flow

---

## Performance Tips

- **Reduce polling**: Change `3000` to `5000` in `dashboard.html` if CPU high
- **Backup database**: Daily backup of `/data/telemetry.db`
- **Monitor logs**: `docker-compose logs | grep -i error`
- **Clean old data**: Database grows ~10MB per year with data every 3s

---

## Security Reminders

⚠️ This is designed for **private LAN only**

For public access, add:
- HTTPS/TLS (Nginx reverse proxy)
- Authentication (JWT/OAuth)
- Rate limiting
- Input validation
- CORS configuration

---

## Version Info

- **Application**: EcoPi OS v2.7
- **Python**: 3.11
- **Flask**: 3.0.0
- **Docker**: Compose v3.8

---

## Next Steps

1. Start with: `docker-compose up -d`
2. Open: `http://localhost:8000`
3. Configure weather station webhook
4. Monitor logs: `docker-compose logs -f`
5. Read full docs: `README.md`, `DEPLOYMENT.md`, `ARCHITECTURE.md`

---

**Last Updated**: June 2026  
**Status**: ✅ Production Ready
