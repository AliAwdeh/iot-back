import threading

from config import APP_CONFIG, INITIAL_RELAY_STATES, INITIAL_UTILITY_STATES

state_lock = threading.Lock()
running = True

config = APP_CONFIG.copy()

gateway = {
    "status": "unknown",
    "last_seen": None,
    "site_id": None,
    "raw": None,
}

sensors = {
    "dht11_1": None,
}

inverters = {
    "must_1": None,
    "must_2": None,
}

relays = {
    "relay_1": {
        "actual_state": "OFF",
        "desired_state": None,
        "applied": None,
        "timestamp": None,
        "published_at": None,
    },
    "relay_2": {
        "actual_state": "ON",
        "desired_state": None,
        "applied": None,
        "timestamp": None,
        "published_at": None,
    },
    "relay_3": {
        "actual_state": "OFF",
        "desired_state": None,
        "applied": None,
        "timestamp": None,
        "published_at": None,
    },
}

relay_states = INITIAL_RELAY_STATES.copy()
utility_states = INITIAL_UTILITY_STATES.copy()

errors = []
history = []
alerts = []
relay_actions = []
maintenance_reports = []

manual_override = {
    "enabled": False,
    "battery_voltage": None,
    "battery_temperature": None,
    "ambient_temperature": None,
    "updated_at": None,
    "updated_by": None,
}

mqtt_client = None
last_seen_mqtt = None
