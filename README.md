# Solar HTTP Backend

This backend connects the Android Solar Monitoring app to the Raspberry Pi gateway.

## Features

- HTTP API for Android
- MQTT bridge to Raspberry Pi
- JWT authentication
- Seed admin account
- Admin user management
- Relay control
- DHT11 telemetry
- MUST inverter telemetry
- Gateway status tracking
- System error tracking
- SQLite storage

## Default Login

Email:

```text
admin@admin.com
```

Password:

```text
test1234
```

## Run

```bash
cd /opt/solar-http
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@admin.com","password":"test1234"}'
```

## Use Token

```bash
curl http://localhost:5000/api/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Main Endpoints

```text
POST /api/auth/login

GET /api/status
GET /api/readings/latest
GET /api/readings/history
GET /api/inverters/main
GET /api/inverters/water
GET /api/inverters/status
GET /api/relays
GET /api/relays/status
POST /api/relays
POST /api/relays/{relay_name}
POST /api/relays/command
GET /api/utility/status
POST /api/utility/status
GET /api/alerts
POST /api/alerts/{alert_id}/ack
GET /api/errors/recent
GET /api/config
GET /api/system/status
POST /api/maintenance/report

GET /api/auth/me
GET /api/admin/users
POST /api/admin/users
POST /api/admin/users/{id}/pause
POST /api/admin/users/{id}/activate
POST /api/admin/users/{id}/disable
DELETE /api/admin/users/{id}
```

## MQTT

Subscribes to:

```text
solar/site1/#
```

Publishes to:

```text
solar/site1/relay/relay_1/desired
solar/site1/relay/relay_2/desired
solar/site1/relay/relay_3/desired
solar/site1/relay/all/get
```

## Security

Before production, set a strong JWT secret:

```bash
export SOLAR_BACKEND_JWT_SECRET="your-long-random-secret"
python app.py
```
