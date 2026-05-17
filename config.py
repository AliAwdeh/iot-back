from pathlib import Path
import os

HOST = "0.0.0.0"
PORT = 5000

SITE_ID = "site1"
DEVICE_ID = "solar_pi_01"

MQTT_BROKER = "192.168.0.223"
MQTT_PORT = 1883
MQTT_USERNAME = None
MQTT_PASSWORD = None
MQTT_ENABLED = True

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "backend_log.txt"
DB_FILE = SCRIPT_DIR / "solar_backend.db"

JWT_SECRET = os.environ.get("SOLAR_BACKEND_JWT_SECRET", "change-this-secret-before-production")
JWT_ISSUER = "solar_backend"
JWT_EXPIRY_SECONDS = 60 * 60 * 24

DEFAULT_ADMIN_EMAIL = "admin@admin.com"
DEFAULT_ADMIN_PASSWORD = "test1234"

APP_CONFIG = {
    "technician_phone": "+96170000000",
    "low_battery_threshold": 11.5,
    "high_ambient_temp_threshold": 45.0,
    "max_current_threshold": 12.0,
    "high_humidity_threshold": 75.0,
}

RELAY_NAME_TO_ID = {
    "water_heater": "relay_1",
    "water_pump": "relay_2",
    "reverse_osmosis": "relay_3",
}

RELAY_ID_TO_NAME = {
    "relay_1": "water_heater",
    "relay_2": "water_pump",
    "relay_3": "reverse_osmosis",
}

INITIAL_RELAY_STATES = {
    "water_heater": False,
    "water_pump": True,
    "reverse_osmosis": False,
}

INITIAL_UTILITY_STATES = {
    "city_electricity": False,
    "generator": False,
}

INVERTER_ROLE_TO_ID = {
    "main": "must_1",
    "water": "must_2",
}

DHT11_STALE_SECONDS = 20
INVERTER_STALE_SECONDS = 30
RELAY_STALE_SECONDS = 60
GATEWAY_STALE_SECONDS = 30
