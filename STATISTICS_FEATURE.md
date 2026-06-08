# Statistics and Historical Data Feature

## Overview
This document describes the new statistics and historical data tracking features added to the Home Automation Dashboard.

## New Features

### 1. Dashboard Tab (Real-time Monitoring)
- **Real-time Metrics**: Displays current solar production, house consumption, and net balance
- **Weather Information**: Temperature, humidity, precipitation, wind speed, and atmospheric pressure
- **Today's Summary Cards**: 
  - Energy Generated (kWh)
  - Energy Consumed (kWh)
  - Energy Sold/Excess (kWh)
- **24-Hour Charts**:
  - Production vs Consumption over the last 24 hours
  - Energy balance visualization
- **Auto-refresh**: Dashboard updates every 3 seconds with latest data

### 2. Historical Tab
- **Daily Statistics Table** (Last 30 periods)
  - Period identifier
  - Total energy generated (kWh)
  - Total energy consumed (kWh)
  - Total energy sold/excess (kWh)
  - Average solar production (W)
  - Average consumption (W)

- **Monthly Statistics Table** (Last 12 months)
  - Month/year identifier
  - Same metrics as daily table

- **Comparison Charts**:
  - Daily vs Monthly generation comparison
  - Daily vs Monthly consumption comparison

## Backend API Endpoints

### GET /api/live
Returns real-time and historical telemetry data.

**Response:**
```json
{
  "latest": {
    "ac_solar_w": 1234.5,
    "house_power_w": 567.8,
    "net_balance": 666.7,
    "temperature": 22.5,
    "humidity": 65,
    "wind_speed": 10.5,
    "wind_dir": 180,
    "barometer": 1013.2,
    "rain_rate": 0.0,
    "solar_rad": 500,
    "uv": 3,
    "timestamp": "14:32:45"
  },
  "history": {
    "timestamps": ["14:30:00", "14:30:30", ...],
    "ac_solar_w": [1200.0, 1220.0, ...],
    "house_power_w": [560.0, 570.0, ...],
    "solar_rad": [500, 502, ...],
    "temperature": [22.4, 22.5, ...]
  }
}
```

### GET /api/summary
Returns aggregated energy statistics for today and current month.

**Response:**
```json
{
  "today": {
    "generated": 12.45,
    "consumed": 18.32,
    "sold": 0.0
  },
  "month": {
    "generated": 234.56,
    "consumed": 312.45,
    "sold": 15.23
  }
}
```

### GET /api/statistics?period=daily|monthly
Returns detailed statistics grouped by period.

**Response for daily:**
```json
{
  "period": "daily",
  "data": [
    {
      "date": "Período 1",
      "generated": 12.45,
      "consumed": 18.32,
      "sold": 0.0,
      "avg_solar": 145.3,
      "avg_consumption": 221.5
    },
    ...
  ]
}
```

## Database Schema
The existing `telemetry` table is used without modifications:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-incrementing primary key |
| timestamp | TEXT | Time in HH:MM:SS format |
| temperature | REAL | Temperature in Celsius |
| humidity | INTEGER | Relative humidity percentage |
| wind_speed | REAL | Wind speed in km/h |
| wind_dir | INTEGER | Wind direction in degrees |
| barometer | REAL | Atmospheric pressure in hPa |
| rain_rate | REAL | Precipitation rate in mm |
| solar_rad | INTEGER | Solar radiation in W/m² |
| uv | INTEGER | UV index |
| ac_solar_w | REAL | Solar production in Watts |
| house_power_w | REAL | House consumption in Watts |
| net_balance | REAL | Net balance (solar - consumption) in Watts |

## Frontend Implementation

### JavaScript Functions

#### updateLiveData()
Fetches `/api/live` and updates real-time metrics, weather info, and charts every 3 seconds.

#### updateTodaySummary()
Fetches `/api/summary` and updates today's energy summary cards.

#### loadStatistics()
Triggered when Historical tab is clicked. Loads both daily and monthly statistics.

#### updateChart24h(history)
Renders a line chart showing solar production vs consumption over time.

#### populateDailyTable(stats)
Renders the daily statistics table with sorted data.

#### populateMonthlyTable(stats)
Renders the monthly statistics table with optional date formatting.

### Energy Unit Handling

The dashboard uses intelligent power unit display:
- **For Power (Watts/Kilowatts)**: Values ≥ 1000W displayed in kW with 2 decimal places
- **For Energy (kWh)**: Always displayed in kWh as returned by API

## Workflow

1. **Dashboard Tab Active** (default):
   - Every 3 seconds: Fetch `/api/live` → Update real-time metrics, weather, charts
   - Also fetch `/api/summary` → Update today's summary cards

2. **User Clicks Historical Tab**:
   - Fetch `/api/statistics?period=daily` → Populate daily table
   - Fetch `/api/statistics?period=monthly` → Populate monthly table
   - Render comparison charts

3. **Data Calculations**:
   - **Generated**: Sum of all `ac_solar_w` values for the period ÷ 1000 = kWh
   - **Consumed**: Sum of all `house_power_w` values for the period ÷ 1000 = kWh
   - **Sold/Excess**: Sum of positive `net_balance` values for the period ÷ 1000 = kWh
   - **Average Solar**: Average of all `ac_solar_w` values for the period in Watts
   - **Average Consumption**: Average of all `house_power_w` values for the period in Watts

## Notes

### Date Handling
Since the original database only stores time (HH:MM:SS) without dates, daily statistics are calculated by:
- Grouping records into chunks (approximately 100 records = 1 period)
- Calculating aggregates for each chunk

### Time Updates
- Real-time updates: 3-second polling interval
- Historical statistics: Loaded on-demand when Historical tab is accessed
- No cache: Always fetches latest data from database

## Configuration
No additional configuration needed. The feature uses existing environment variables:
- `DB_PATH`: Path to SQLite database file
- `TZ`: Timezone (default: Europe/Lisbon)

## Future Improvements
1. Add actual date field to database for more accurate historical tracking
2. Implement configurable polling intervals for statistics
3. Add export functionality (CSV, PDF) for reports
4. Implement trend analysis and anomaly detection
5. Add customizable date range filters
