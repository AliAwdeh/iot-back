# Solar Monitoring Backend Code Documentation

## 1. Project Overview

This project is a Python backend for a solar monitoring and control system. It connects an Android mobile application to a Raspberry Pi gateway. The Raspberry Pi reads data from solar hardware, sensors, and relay controllers, then publishes that data through MQTT. The backend receives this MQTT data, stores it in SQLite, exposes it through HTTP APIs, and allows authenticated users to control relays.

The backend is designed for a local IoT installation. It does not use a large web framework such as Flask or Django. Instead, it uses Python standard library components such as `http.server`, `sqlite3`, `threading`, and custom modules for authentication, MQTT handling, relay logic, and data normalization.

The main responsibilities of the backend are:

- Receive telemetry from the Raspberry Pi through MQTT.
- Store system data in a local SQLite database.
- Provide REST-like HTTP endpoints for the Android application.
- Authenticate users using JWT tokens.
- Allow admin user management.
- Control physical relays through MQTT commands.
- Calculate a clean latest-status response for the app.
- Support fail-safe behavior when inverter readings are unavailable.

## 2. Main System Architecture

The system has three main parts:

```text
Android App <-> HTTP Backend <-> MQTT Broker <-> Raspberry Pi Gateway <-> Hardware
```

The Android app communicates only with the backend using HTTP. The backend communicates with the Raspberry Pi through MQTT. The Raspberry Pi is responsible for reading the hardware, while the backend is responsible for storage, authentication, API responses, and relay command forwarding.

The main backend entry point is:

```text
app.py
```

When the backend starts, it performs the following sequence:

1. Initializes the SQLite database.
2. Restores the last known MQTT state from SQLite.
3. Starts the MQTT client.
4. Generates an initial latest-status snapshot.
5. Starts the HTTP server.
6. Starts the local command-line interface thread.

This startup sequence is important because the backend stores live telemetry in memory. If the server restarts, memory is cleared. The restore step loads the latest saved gateway, inverter, sensor, and relay data from SQLite so the API does not immediately return empty data after a restart.

## 3. File Structure

The backend is split into small modules, each with a specific responsibility.

| File | Purpose |
|---|---|
| `app.py` | Starts the backend, initializes database/MQTT/HTTP server, and handles shutdown. |
| `config.py` | Stores constants such as ports, MQTT broker address, relay mapping, thresholds, and file paths. |
| `state.py` | Stores live in-memory state shared between modules. |
| `http_server.py` | Defines all HTTP API endpoints and request handling logic. |
| `mqtt_service.py` | Connects to MQTT, subscribes to topics, receives telemetry, and updates state/database. |
| `database.py` | Creates SQLite tables and provides database helper functions. |
| `readings.py` | Builds the latest analytics/status response returned to the Android app. |
| `relays.py` | Handles relay mapping, active-low relay behavior, and MQTT relay commands. |
| `normalizers.py` | Converts raw MQTT payloads into stable backend data structures. |
| `auth.py` | Handles password hashing and JWT creation/validation. |
| `state_restore.py` | Restores latest state from SQLite after restart. |
| `cli.py` | Provides a local terminal menu for debugging and relay control. |
| `utils.py` | Provides helper functions for timestamps, logging, conversion, and stale checks. |
| `API_ENDPOINTS.md` | Endpoint-level API documentation. |

## 4. Configuration

The main configuration is stored in `config.py`.

Important configuration values include:

```python
HOST = "0.0.0.0"
PORT = 5000
MQTT_BROKER = "192.168.0.223"
MQTT_PORT = 1883
SITE_ID = "site1"
DEVICE_ID = "solar_pi_01"
```

The backend listens on all network interfaces using `0.0.0.0`, which allows devices on the local network to access it using the server IP address.

The backend also defines application thresholds:

```python
APP_CONFIG = {
    "technician_phone": "+96170000000",
    "low_battery_threshold": 45,
    "high_ambient_temp_threshold": 45.0,
    "max_current_threshold": 12.0,
    "high_humidity_threshold": 75.0,
}
```

These values are returned to the app through `/api/config`. They help the app decide when to show warnings or notifications.

## 5. Relay Mapping

Relay mapping is defined in `config.py`.

```python
RELAY_NAME_TO_ID = {
    "water_pump": "relay_1",
    "reverse_osmosis": "relay_2",
    "water_heater": "relay_3",
}
```

The reverse mapping is:

```python
RELAY_ID_TO_NAME = {
    "relay_1": "water_pump",
    "relay_2": "reverse_osmosis",
    "relay_3": "water_heater",
}
```

This means the Android app can use readable names like `water_pump`, while the backend translates them to physical relay IDs used by the Raspberry Pi.

The water pump uses active-low logic. This means the logical app state is inverted compared to the physical relay state:

```text
water_pump ON  -> physical relay_1 OFF
water_pump OFF -> physical relay_1 ON
```

This behavior is implemented in `relays.py` using:

```python
INVERTED_LOGIC_RELAYS = {"water_pump"}
```

This is important because it allows the app to show the real device meaning, while the backend handles the electrical relay behavior internally.

## 6. Runtime State

The file `state.py` stores the live runtime state of the backend. This includes:

- Gateway status.
- Sensor readings.
- Inverter readings.
- Relay states.
- Utility states.
- System errors.
- Alerts.
- Manual override values.
- MQTT connection object.

Example state sections:

```python
gateway = {
    "status": "unknown",
    "last_seen": None,
    "site_id": None,
    "raw": None,
}
```

```python
inverters = {
    "must_1": None,
    "must_2": None,
}
```

The backend uses a thread lock:

```python
state_lock = threading.Lock()
```

This is needed because both the HTTP server and MQTT client can access or update the same state at the same time.

## 7. Database Design

The backend uses SQLite as a local database. The database file path is defined in `config.py`:

```python
DB_FILE = SCRIPT_DIR / "solar_backend.db"
```

The database is initialized in `database.py` by `init_db()`.

Main tables include:

| Table | Purpose |
|---|---|
| `users` | Stores user accounts, roles, statuses, and password hashes. |
| `latest_state` | Stores latest MQTT state for restore after restart. |
| `mqtt_messages` | Stores raw MQTT messages. |
| `readings` | Stores computed latest-status snapshots. |
| `inverter_readings` | Stores normalized inverter readings. |
| `sensor_readings` | Stores DHT11 readings. |
| `relay_actions` | Stores relay command history. |
| `system_errors` | Stores system errors from MQTT. |
| `alerts` | Stores alert records. |

The `latest_state` table is especially important. It allows the backend to recover the last received gateway, sensor, inverter, and relay state after a restart.

## 8. Authentication

Authentication is handled in `auth.py`.

Passwords are stored using PBKDF2 hashing:

```python
hashlib.pbkdf2_hmac("sha256", ...)
```

Each password hash is stored with a random salt:

```text
salt$password_hash
```

The backend creates JWT tokens manually using:

- Base64 URL encoding.
- HMAC SHA-256 signature.
- Expiration time.
- Issuer validation.

The JWT payload includes:

```json
{
  "iss": "solar_backend",
  "iat": 1234567890,
  "exp": 1234654290,
  "user_id": 1,
  "email": "admin@admin.com",
  "role": "admin",
  "status": "active"
}
```

All endpoints except login require:

```http
Authorization: Bearer TOKEN
```

The default admin user is automatically created when the database is initialized.

## 9. HTTP API Layer

HTTP endpoints are implemented in `http_server.py` using Python's `BaseHTTPRequestHandler`.

The server supports:

- `GET`
- `POST`
- `DELETE`
- `OPTIONS`

It also adds CORS headers so the Android app or other clients can access the API.

Important endpoint groups:

- Authentication endpoints.
- Latest readings and history endpoints.
- Inverter endpoints.
- Relay endpoints.
- Utility status endpoints.
- Alert and error endpoints.
- Admin user management endpoints.
- Manual override endpoint.

The full endpoint reference is documented separately in:

```text
API_ENDPOINTS.md
```

## 10. MQTT Data Flow

MQTT communication is handled by `mqtt_service.py`.

The backend subscribes to:

```text
solar/site1/#
```

This means it receives all MQTT messages under the `solar/site1` topic tree.

Important MQTT topics include:

```text
solar/site1/system/status
solar/site1/system/errors
solar/site1/sensor/dht11_1/telemetry
solar/site1/inverter/must_1/telemetry
solar/site1/inverter/must_2/telemetry
solar/site1/relay/all/status
solar/site1/relay/relay_1/status
solar/site1/relay/relay_2/status
solar/site1/relay/relay_3/status
```

When an MQTT message arrives:

1. The raw JSON is parsed.
2. The message is logged.
3. The raw MQTT message is inserted into SQLite.
4. The topic is matched to a handler.
5. The handler normalizes the data.
6. Runtime state is updated.
7. Latest state is saved to SQLite.
8. Specialized tables such as `inverter_readings` or `sensor_readings` are updated.

This allows both real-time API responses and historical storage.

## 11. Data Normalization

Raw MQTT payloads from the Raspberry Pi may contain different field names depending on the hardware reader version. The file `normalizers.py` converts these raw payloads into stable backend structures.

For inverter data, it supports both newer and older field names:

```python
panel_voltage = payload.get("pv_voltage", payload.get("panel_voltage"))
load_power_w = payload.get("load_power_w", payload.get("load_power", payload.get("active_power_w")))
```

The normalizer also fixes a known battery-voltage issue. Sometimes the top-level field reports:

```json
"battery_voltage": 0.0
```

while the correct value exists inside:

```json
"inverter_data": {
  "inverter_battery_voltage": 57.9
}
```

The backend falls back to that nested value when the top-level battery voltage is zero.

## 12. Latest Analytics Calculation

The latest status response is built in `readings.py` by `latest_status()`.

This function combines:

- Gateway status.
- Inverter readings.
- DHT11 sensor readings.
- Relay states.
- Utility states.
- Stale-data flags.
- Manual override values.

The response is returned by:

```text
GET /api/status
GET /api/readings/latest
```

The backend prefers the water inverter for top-level analytics when it has valid data. If the water inverter is unavailable, the backend enters a fail-safe mode.

The top-level analytics include:

```json
{
  "battery_voltage": 57.7,
  "panel_voltage": 136.1,
  "current": 26.4,
  "load_current": 26.4,
  "battery_temperature": 66.0,
  "ambient_temperature": 29.0,
  "humidity": 20.0,
  "system_status": "NORMAL"
}
```

Each generated latest-status response is also inserted into the `readings` table. This makes it available through the historical readings endpoint.

## 13. Water Inverter Fail-Safe

The water inverter is considered prone to being off or unavailable. For that reason, the backend includes fail-safe logic.

The function `inverter_has_readings()` checks whether an inverter has valid data. It rejects inverter data when:

- The inverter object is missing.
- Status is not `ok` or `normal`.
- The work state indicates off or shutdown.
- The timestamp is stale.
- Important numeric fields are all zero.

If the water inverter has valid readings, the latest response uses water inverter values.

If the water inverter does not have valid readings but the main inverter does, the backend:

- Uses main inverter battery voltage and system status.
- Sets water-specific load fields to zero.
- Marks the summary source as `main_inverter_water_failsafe`.

If neither inverter has valid readings, the backend returns:

```json
"system_status": "NO_DATA"
```

and zeroes for the main analytics values.

## 14. System Status Correction

Some raw inverter payloads may report:

```json
"system_status": "LOW_BATTERY"
```

even when the voltage is invalid or the inverter read failed.

The backend corrects this using `get_inverter_system_status()`:

- If the inverter has no valid readings, the status becomes `NO_DATA`.
- If battery voltage is above `low_battery_threshold`, a false `LOW_BATTERY` is changed to `NORMAL`.
- If battery voltage is valid and less than or equal to the threshold, the status is `LOW_BATTERY`.

This prevents false low-battery alarms when the inverter returned an invalid all-zero reading.

## 15. Manual Override

The backend includes a manual override feature for testing or emergency operation.

Endpoint:

```text
POST /api/override/readings
```

It can manually set:

- Battery voltage.
- Battery temperature.
- Ambient temperature.

When enabled, the latest response returns:

```json
"system_status": "OVERRIDE"
```

and the selected manual values replace the automatically calculated values.

The override can be disabled with:

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

This feature is useful for testing app behavior without changing the physical hardware.

## 16. Relay Control

Relay control is handled in `relays.py`.

The backend accepts relay commands through HTTP and publishes MQTT commands to the Raspberry Pi.

For example, when the app sends:

```json
{
  "water_pump": true
}
```

the backend translates this to the physical relay command. Because water pump is active-low, `true` becomes physical relay `OFF`.

Relay command responses include an updated analytics object:

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

Relay actions are also saved in the `relay_actions` table.

## 17. Historical Data

Historical data is stored in SQLite.

The endpoint:

```text
GET /api/readings/history
```

returns readings from the `readings` table.

It supports:

```text
limit
period
range
```

Examples:

```text
/api/readings/history?limit=100
/api/readings/history?period=hour
/api/readings/history?period=day
/api/readings/history?period=week
/api/readings/history?period=month
```

If no readings are available for a selected period, the backend returns:

```json
-1
```

This allows the Android app to distinguish between an empty data set and a valid historical response.

## 18. State Restore After Restart

The file `state_restore.py` solves an important reliability problem.

Because live data is stored in memory, restarting the backend would normally cause:

```json
"main_inverter": null,
"water_inverter": null,
"dht11": null
```

even though the SQLite database already contains the latest values.

To fix this, `restore_latest_state_from_db()` loads the latest saved values from the `latest_state` table and restores:

- Gateway status.
- Main inverter state.
- Water inverter state.
- DHT11 sensor state.
- Relay states.
- Last seen MQTT timestamp.

This makes the API useful immediately after startup, even before a new MQTT message is received.

## 19. Error Handling And Logging

The backend logs events using `log_event()` from `utils.py`.

Each log line includes a timestamp:

```text
2026-05-18T12:00:00 | MQTT connected to 192.168.0.223:1883
```

Logs are printed to the console and written to:

```text
backend_log.txt
```

The backend records:

- HTTP requests.
- MQTT connection events.
- MQTT received messages.
- Relay commands.
- Database failures.
- System errors received from MQTT.

Recent system errors are available through:

```text
GET /api/errors/recent
```

## 20. Local CLI

The file `cli.py` provides a small terminal interface that runs in a background thread when the backend starts.

It allows a developer/operator to:

- Print the latest full status.
- View main inverter data.
- View water inverter data.
- View DHT11 data.
- View relay states.
- Request relay status.
- Edit technician phone.
- Send relay ON/OFF commands.
- View gateway status.
- View recent errors.

This CLI is useful during development and debugging but is not the main interface for the Android app.

## 21. Security Considerations

The backend uses JWT authentication and password hashing, but there are still production security points to consider.

Important notes:

- The default admin account should be changed for production.
- `SOLAR_BACKEND_JWT_SECRET` should be set to a strong random value.
- The backend currently allows CORS from all origins.
- The backend uses local SQLite storage, so file permissions should be protected.
- Admin endpoints should only be used by trusted accounts.
- Manual override should be used carefully because it changes the data returned by latest analytics.

Recommended production setup:

```bash
export SOLAR_BACKEND_JWT_SECRET="long-random-secret"
```

## 22. Example Full Data Flow

Example: DHT11 sensor reading

1. Raspberry Pi reads temperature and humidity.
2. Raspberry Pi publishes MQTT message:

```text
solar/site1/sensor/dht11_1/telemetry
```

3. Backend receives the MQTT message in `mqtt_service.py`.
4. Payload is normalized by `normalize_dht11_payload()`.
5. Runtime state is updated in `state.sensors`.
6. Latest state is saved in SQLite.
7. Sensor reading is inserted into `sensor_readings`.
8. Android app calls `/api/readings/latest`.
9. Backend returns `ambient_temperature` and `humidity`.

Example: Relay control

1. Android app sends `POST /api/relays/water_pump`.
2. Backend authenticates the JWT token.
3. Backend maps `water_pump` to `relay_1`.
4. Backend applies active-low conversion.
5. Backend publishes MQTT command to the Raspberry Pi.
6. Backend stores the relay action.
7. Backend returns updated analytics.
8. Raspberry Pi applies the physical relay command.
9. Raspberry Pi publishes relay status back to MQTT.
10. Backend updates relay state.

## 23. Summary

This backend acts as the central software bridge between the Android monitoring app and the Raspberry Pi solar gateway. It handles real-time MQTT telemetry, authenticated HTTP APIs, local SQLite persistence, relay control, data normalization, fail-safe analytics, and historical data retrieval.

The code is organized into clear modules, making it suitable for an IoT university project. The design keeps hardware communication separate from app communication, which improves maintainability and makes the system easier to debug.

