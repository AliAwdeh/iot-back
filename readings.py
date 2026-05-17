import state

from config import (
    DEVICE_ID,
    SITE_ID,
    RELAY_ID_TO_NAME,
    DHT11_STALE_SECONDS,
    INVERTER_STALE_SECONDS,
    RELAY_STALE_SECONDS,
    GATEWAY_STALE_SECONDS,
)
from database import db_insert_reading
from normalizers import relay_state_to_bool
from utils import iso_now, is_stale, to_float


def get_main_inverter():
    return state.inverters.get("must_1")


def get_water_inverter():
    return state.inverters.get("must_2")


def get_dht11():
    return state.sensors.get("dht11_1")


def get_relay_booleans():
    relay_states = {}

    for relay_id, relay_data in state.relays.items():
        relay_name = RELAY_ID_TO_NAME.get(relay_id)

        if relay_name:
            relay_state = relay_data.get("desired_state") or relay_data.get("actual_state")
            relay_states[relay_name] = relay_state_to_bool(relay_state)

    return relay_states


def infer_utility_states(main_inverter):
    grid_voltage = 0.0

    if main_inverter:
        grid_voltage = to_float(main_inverter.get("grid_voltage"))

    return {
        "city_electricity": grid_voltage > 150,
        "generator": False,
    }


def get_inverter_battery_voltage(inverter):
    if not inverter:
        return 0.0

    battery_voltage = to_float(inverter.get("battery_voltage"))

    if battery_voltage > 0:
        return battery_voltage

    raw = inverter.get("raw") or {}
    inverter_data = raw.get("inverter_data") or {}

    return to_float(inverter_data.get("inverter_battery_voltage"), battery_voltage)


def get_stale_flags():
    main = get_main_inverter()
    water = get_water_inverter()
    dht = get_dht11()

    relay_timestamps = [
        relay.get("received_at") or relay.get("timestamp") or relay.get("published_at")
        for relay in state.relays.values()
        if relay
    ]

    relays_stale = True

    if relay_timestamps:
        relays_stale = any(is_stale(ts, RELAY_STALE_SECONDS) for ts in relay_timestamps)

    return {
        "gateway": is_stale(state.last_seen_mqtt, GATEWAY_STALE_SECONDS),
        "dht11": is_stale(dht.get("received_at") or dht.get("timestamp") if dht else None, DHT11_STALE_SECONDS),
        "main_inverter": is_stale(
            main.get("received_at") or main.get("timestamp") if main else None,
            INVERTER_STALE_SECONDS,
        ),
        "water_inverter": is_stale(
            water.get("received_at") or water.get("timestamp") if water else None,
            INVERTER_STALE_SECONDS,
        ),
        "relays": relays_stale,
    }


def latest_status():
    with state.state_lock:
        main = get_main_inverter()
        water = get_water_inverter()
        dht = get_dht11()
        solar_source = water or main

        if solar_source:
            battery_voltage = get_inverter_battery_voltage(solar_source)
            panel_voltage = to_float(solar_source.get("pv_voltage"))
            current = to_float(solar_source.get("load_current"))
            battery_temperature = to_float(solar_source.get("inverter_temperature_c"))
            system_status = solar_source.get("system_status") or "UNKNOWN"
        else:
            battery_voltage = 0.0
            panel_voltage = 0.0
            current = 0.0
            battery_temperature = 0.0
            system_status = "NO_DATA"

        if dht and dht.get("status") == "ok":
            ambient_temperature = to_float(dht.get("temperature_c"))
            humidity = to_float(dht.get("humidity_percent"))
        else:
            ambient_temperature = 0.0
            humidity = 0.0

        relay_states = get_relay_booleans()
        utility_states = infer_utility_states(main)

        state.utility_states.update(utility_states)

        stale = get_stale_flags()

        reading = {
            "device_id": DEVICE_ID,
            "site_id": SITE_ID,
            "timestamp": iso_now(),

            "gateway_status": state.gateway.get("status", "unknown"),
            "gateway_last_seen": state.gateway.get("last_seen"),
            "gateway_site_id": state.gateway.get("site_id"),

            "battery_voltage": battery_voltage,
            "panel_voltage": panel_voltage,
            "current": current,
            "load_current": current,
            "battery_temperature": battery_temperature,
            "ambient_temperature": ambient_temperature,
            "humidity": humidity,
            "system_status": system_status,

            "relay_states": relay_states,
            "utility_states": state.utility_states.copy(),

            "main_inverter": main,
            "water_inverter": water,
            "dht11": dht,

            "data_fresh": not any(stale.values()),
            "stale": stale,

            "data_sources": {
                "summary": "water_inverter",
                "main_inverter": "must_1_usb0",
                "water_inverter": "must_2_usb1",
                "environment_sensor": "dht11_1",
                "relay_controller": "raspberry_pi_pico_serial",
            },
        }

        state.history.append(reading)

        if len(state.history) > 300:
            state.history.pop(0)

    db_insert_reading(reading)
    return reading


def latest_reading():
    return latest_status()
