# Solar Backend API Endpoints

Base URL:

```text
http://SERVER_IP:5000
```

All endpoints are under `/api`.

## Authentication

All endpoints require a JWT bearer token except `POST /api/auth/login`.

Use the token like this:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Default admin account:

```text
email: admin@admin.com
password: test1234
```

## Response Notes

- Responses are JSON.
- Relay command responses include refreshed `analytics`.
- `/api/readings/history` reads persisted data from SQLite.
- Water inverter fail-safe is enabled:
  - If water inverter has valid readings, top-level solar analytics use it.
  - If water inverter is off/missing/stale/all-zero, top-level water-load fields return `0.0`.
  - Shared inverter info can fall back to main inverter only when main has valid readings.
- `system_status` is corrected by backend:
  - Invalid/no-readings inverter data returns `NO_DATA`.
  - Valid battery voltage above `low_battery_threshold` overrides false `LOW_BATTERY` to `NORMAL`.
  - Valid battery voltage at or below `low_battery_threshold` returns `LOW_BATTERY`.

## Relay Mapping

Physical relay IDs:

```text
relay_1 -> water_pump
relay_2 -> reverse_osmosis
relay_3 -> water_heater
```

The water pump is active-low:

```text
water_pump ON  -> physical relay_1 OFF
water_pump OFF -> physical relay_1 ON
```

## Auth Endpoints

### POST `/api/auth/login`

Public endpoint. Logs in a user and returns a JWT.

Request:

```json
{
  "email": "admin@admin.com",
  "password": "test1234"
}
```

Success response:

```json
{
  "success": true,
  "message": "Login successful",
  "token_type": "Bearer",
  "access_token": "JWT_TOKEN",
  "expires_in_seconds": 86400,
  "user": {
    "id": 1,
    "email": "admin@admin.com",
    "role": "admin",
    "status": "active"
  }
}
```

Errors:

- `400` missing email/password
- `401` invalid credentials
- `403` account paused/disabled

### GET `/api/auth/me`

Returns the currently authenticated user.

Success response:

```json
{
  "authenticated": true,
  "user": {
    "id": 1,
    "email": "admin@admin.com",
    "role": "admin",
    "status": "active"
  }
}
```

## Connectivity

### GET `/api/connect`

Checks backend connectivity.

Success response:

```json
{
  "success": true,
  "message": "Backend connection successful. Ready to transmit solar data.",
  "timestamp": "2026-05-18T12:00:00",
  "bind_host": "0.0.0.0",
  "port": 5000,
  "authenticated_as": "admin@admin.com"
}
```

## Readings And Analytics

### GET `/api/status`

Alias for latest analytics. Same response as `GET /api/readings/latest`.

### GET `/api/readings/latest`

Returns the latest computed analytics from in-memory MQTT state.

Important top-level fields:

```json
{
  "device_id": "solar_pi_01",
  "site_id": "site1",
  "timestamp": "2026-05-18T12:00:00",
  "gateway_status": "online",
  "battery_voltage": 57.7,
  "panel_voltage": 136.1,
  "current": 26.4,
  "load_current": 26.4,
  "battery_temperature": 66.0,
  "ambient_temperature": 29.0,
  "humidity": 20.0,
  "system_status": "NORMAL",
  "relay_states": {
    "water_pump": true,
    "reverse_osmosis": false,
    "water_heater": false
  },
  "utility_states": {
    "city_electricity": true,
    "generator": false
  },
  "main_inverter": {},
  "water_inverter": {},
  "water_inverter_has_readings": true,
  "main_inverter_has_readings": true,
  "dht11": {},
  "data_fresh": true,
  "stale": {
    "gateway": false,
    "dht11": false,
    "main_inverter": false,
    "water_inverter": false,
    "relays": false
  },
  "data_sources": {
    "summary": "water_inverter",
    "main_inverter": "must_1_usb0",
    "water_inverter": "must_2_usb1",
    "environment_sensor": "dht11_1",
    "relay_controller": "raspberry_pi_pico_serial"
  }
}
```

Possible `data_sources.summary` values:

```text
water_inverter
main_inverter_water_failsafe
no_valid_inverter_data
```

### GET `/api/readings/history`

Returns persisted historical readings from SQLite.

Query parameters:

```text
limit   optional, default 100
period  optional: minute, hour, day, week, month
range   optional alias for period
```

Examples:

```http
GET /api/readings/history
GET /api/readings/history?limit=50
GET /api/readings/history?period=hour
GET /api/readings/history?period=day&limit=500
GET /api/readings/history?range=month
```

Success response when data exists:

```json
[
  {
    "id": 123,
    "timestamp": "2026-05-18T12:00:00",
    "battery_voltage": 57.7,
    "panel_voltage": 136.1,
    "relay_states": {
      "water_pump": true,
      "reverse_osmosis": false,
      "water_heater": false
    }
  }
]
```

If no data exists for the selected period:

```json
-1
```

Errors:

- `400` invalid `limit`
- `400` invalid `period`

## Inverter Endpoints

### GET `/api/inverters/main`

Returns current main inverter state, mapped from `must_1`.

Returns `{}` if no main inverter data is available.

### GET `/api/inverters/water`

Returns current water inverter state, mapped from `must_2`.

Returns `{}` if no water inverter data is available.

### GET `/api/inverters/status`

Returns both inverter objects and mapping metadata.

Success response:

```json
{
  "main_inverter": {},
  "water_inverter": {},
  "mapping": {
    "must_1": "USB0 main solar inverter",
    "must_2": "USB1 water inverter"
  }
}
```

## Relay Endpoints

### GET `/api/relays`

Requests relay statuses over MQTT and returns current relay state.

Same response as `GET /api/relays/status`.

### GET `/api/relays/status`

Returns current relay state.

Success response:

```json
{
  "relay_states": {
    "water_pump": true,
    "reverse_osmosis": false,
    "water_heater": false
  },
  "raw_relays": {
    "relay_1": "OFF",
    "relay_2": "OFF",
    "relay_3": "OFF"
  },
  "relay_details": {
    "relay_1": {
      "actual_state": "OFF",
      "desired_state": null
    }
  }
}
```

### POST `/api/relays`

Sends multiple relay commands.

Request:

```json
{
  "water_pump": true,
  "reverse_osmosis": false,
  "water_heater": false
}
```

Success response:

```json
{
  "success": true,
  "message": "Relay commands sent",
  "commands_sent": [
    {
      "relay_name": "water_pump",
      "relay_id": "relay_1",
      "desired_state": "ON",
      "physical_desired_state": "OFF"
    }
  ],
  "analytics": {}
}
```

Unknown relay names are ignored in this endpoint.

### POST `/api/relays/{relay_name}`

Sends one relay command by relay name.

Valid relay names:

```text
water_pump
reverse_osmosis
water_heater
```

Request:

```json
{
  "state": true
}
```

Success response:

```json
{
  "success": true,
  "message": "Relay command sent",
  "relay_name": "water_pump",
  "relay_id": "relay_1",
  "desired_state": "ON",
  "physical_desired_state": "OFF",
  "analytics": {}
}
```

Errors:

- `400` unknown relay name
- `400` missing `state`

### POST `/api/relays/command`

Alternative relay command format.

Request:

```json
{
  "target": "water_pump",
  "action": "ON",
  "source": "android_app"
}
```

Success response:

```json
{
  "success": true,
  "message": "Relay command sent",
  "relay_name": "water_pump",
  "relay_id": "relay_1",
  "desired_state": "ON",
  "physical_desired_state": "OFF",
  "analytics": {}
}
```

Errors:

- `400` unknown relay name
- `400` invalid relay state

## Utility Endpoints

### GET `/api/utility/status`

Returns utility states.

Success response:

```json
{
  "city_electricity": true,
  "generator": false
}
```

### POST `/api/utility/status`

Updates utility states.

Request:

```json
{
  "city_electricity": true,
  "generator": false
}
```

Success response:

```json
{
  "success": true,
  "message": "Utility state updated",
  "utility_states": {
    "city_electricity": true,
    "generator": false
  }
}
```

## Alerts And Errors

### GET `/api/alerts`

Returns the latest 100 in-memory alerts.

Success response:

```json
[]
```

### POST `/api/alerts/{alert_id}/ack`

Acknowledges an alert by ID.

Success response:

```json
{
  "success": true,
  "message": "Alert acknowledged"
}
```

Errors:

- `400` invalid alert ID
- `404` alert not found

### GET `/api/errors/recent`

Returns the latest 100 in-memory system errors.

Success response:

```json
[]
```

## Config

### GET `/api/config`

Returns app configuration.

Success response:

```json
{
  "technician_phone": "+96170000000",
  "low_battery_threshold": 45,
  "high_ambient_temp_threshold": 45.0,
  "max_current_threshold": 12.0,
  "high_humidity_threshold": 75.0
}
```

Notes:

- Temperature notifications should use `ambient_temperature`, not `battery_temperature`.
- Low battery logic uses top-level `battery_voltage` and `low_battery_threshold`.

## Manual Override

### POST `/api/override/readings`

Enables or updates a manual readings override. When enabled, `/api/readings/latest` returns the manual values for the provided fields and sets:

```json
"system_status": "OVERRIDE"
```

It also sets:

```json
"data_sources": {
  "summary": "manual_override"
}
```

Request:

```json
{
  "battery_voltage": 50.5,
  "battery_temperature": 31.2,
  "ambient_temperature": 27.8
}
```

At least one of these fields is required:

```text
battery_voltage
battery_temperature
ambient_temperature
```

Success response:

```json
{
  "success": true,
  "message": "Manual readings override enabled",
  "override": {
    "enabled": true,
    "battery_voltage": 50.5,
    "battery_temperature": 31.2,
    "ambient_temperature": 27.8,
    "updated_at": "2026-05-18T16:25:14",
    "updated_by": "admin@admin.com"
  },
  "analytics": {
    "battery_voltage": 50.5,
    "battery_temperature": 31.2,
    "ambient_temperature": 27.8,
    "system_status": "OVERRIDE"
  }
}
```

Disable override:

```json
{
  "enabled": false
}
```

or:

```json
{
  "clear": true
}
```

Disable response:

```json
{
  "success": true,
  "message": "Manual readings override disabled",
  "override": {
    "enabled": false,
    "battery_voltage": null,
    "battery_temperature": null,
    "ambient_temperature": null
  },
  "analytics": {}
}
```

Errors:

- `400` no override fields provided
- `400` invalid numeric value

## System

### GET `/api/system/status`

Returns backend and gateway health.

Success response:

```json
{
  "backend_online": true,
  "mqtt_connected": true,
  "last_seen_mqtt": "2026-05-18T12:00:00",
  "gateway_status": "online",
  "gateway_last_seen": "2026-05-18T12:00:00",
  "gateway_site_id": "site1",
  "gateway": {},
  "has_main_inverter_data": true,
  "has_water_inverter_data": true,
  "has_dht11_data": true
}
```

## Maintenance

### POST `/api/maintenance/report`

Stores a maintenance report in memory.

Request can contain any JSON fields:

```json
{
  "technician": "Name",
  "notes": "Checked relays and inverter wiring"
}
```

Success response:

```json
{
  "success": true,
  "message": "Maintenance report saved"
}
```

## Admin User Management

Admin role required.

### GET `/api/admin/users`

Returns all users.

Success response:

```json
{
  "success": true,
  "users": [
    {
      "id": 1,
      "email": "admin@admin.com",
      "role": "admin",
      "status": "active",
      "created_at": "2026-05-18T12:00:00",
      "updated_at": "2026-05-18T12:00:00"
    }
  ]
}
```

### POST `/api/admin/users`

Creates a user.

Request:

```json
{
  "email": "user@example.com",
  "password": "password123",
  "role": "user",
  "status": "active"
}
```

Valid roles:

```text
admin
user
```

Valid statuses:

```text
active
paused
disabled
```

Success response:

```json
{
  "success": true,
  "message": "User created",
  "user": {
    "id": 2,
    "email": "user@example.com",
    "role": "user",
    "status": "active"
  }
}
```

Errors:

- `400` missing email/password
- `400` invalid role/status
- `400` duplicate email
- `403` admin access required

### POST `/api/admin/users/{id}/pause`

Sets user status to `paused`.

Success response:

```json
{
  "success": true,
  "message": "User status updated"
}
```

### POST `/api/admin/users/{id}/activate`

Sets user status to `active`.

Success response:

```json
{
  "success": true,
  "message": "User status updated"
}
```

### POST `/api/admin/users/{id}/disable`

Sets user status to `disabled`.

Success response:

```json
{
  "success": true,
  "message": "User status updated"
}
```

### DELETE `/api/admin/users/{id}`

Deletes a user.

The logged-in user cannot delete their own account.

Success response:

```json
{
  "success": true,
  "message": "User deleted"
}
```

Errors:

- `400` user not found
- `400` cannot delete own account
- `403` admin access required

## CORS And OPTIONS

All endpoints support CORS headers:

```text
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Methods: GET,POST,DELETE,OPTIONS
```

`OPTIONS` returns `204`.

## Common Error Responses

Missing auth:

```json
{
  "success": false,
  "message": "Missing Authorization header. Use: Bearer token"
}
```

Invalid/expired token:

```json
{
  "success": false,
  "message": "Invalid token"
}
```

Not found:

```json
{
  "error": "Not found",
  "path": "/api/unknown"
}
```
