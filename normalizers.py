from utils import to_float


def normalize_inverter_payload(payload):
    """
    Converts Raspberry Pi inverter payload into a stable backend shape.

    Supports both the new documentation field names and the older field names.
    """

    device_id = payload.get("device_id")
    role = payload.get("role")

    panel_voltage = payload.get("pv_voltage", payload.get("panel_voltage"))
    panel_power = payload.get("pv_power", payload.get("panel_power"))
    charger_current = payload.get("pv_current", payload.get("charger_current"))

    inverter_voltage = payload.get("ac_output_voltage", payload.get("inverter_voltage"))
    inverter_frequency = payload.get("ac_output_frequency", payload.get("inverter_frequency"))

    load_power_w = payload.get("load_power_w", payload.get("load_power", payload.get("active_power_w")))
    inverter_temperature = payload.get(
        "inverter_temperature_c",
        payload.get("dc_radiator_temperature", payload.get("dc_radiator_temperature_c")),
    )
    battery_voltage = to_float(payload.get("battery_voltage"))

    if battery_voltage <= 0:
        inverter_data = payload.get("inverter_data") or {}
        battery_voltage = to_float(inverter_data.get("inverter_battery_voltage"), battery_voltage)

    work_state = payload.get(
        "work_state",
        payload.get("inverter_work_state_text"),
    )

    return {
        "device_type": payload.get("device_type", "must_inverter"),
        "device_id": device_id,
        "name": payload.get("name"),
        "role": role,
        "port": payload.get("port"),
        "slave_address": payload.get("slave_address"),
        "baudrate": payload.get("baudrate"),

        "status": payload.get("status", "UNKNOWN"),
        "system_status": payload.get("system_status", "UNKNOWN"),

        "battery_voltage": battery_voltage,
        "pv_voltage": to_float(panel_voltage),
        "pv_current": to_float(charger_current),
        "pv_power": to_float(panel_power),

        "ac_output_voltage": to_float(inverter_voltage),
        "ac_output_frequency": to_float(inverter_frequency),

        "grid_voltage": to_float(payload.get("grid_voltage")),
        "grid_frequency": to_float(payload.get("grid_frequency")),

        "bus_voltage": to_float(payload.get("bus_voltage")),
        "load_percent": to_float(payload.get("load_percent")),
        "load_power_w": to_float(load_power_w),
        "load_current": to_float(payload.get("load_current")),

        "inverter_temperature_c": to_float(inverter_temperature),
        "work_state": work_state,

        "timestamp": payload.get("timestamp"),
        "published_at": payload.get("published_at"),

        "errors": payload.get("errors", payload.get("read_errors", {})),
        "raw": payload,
    }


def normalize_dht11_payload(payload):
    return {
        "device_type": payload.get("device_type", "dht11"),
        "device_id": payload.get("device_id", "dht11_1"),
        "temperature_c": to_float(payload.get("temperature_c")),
        "humidity_percent": to_float(payload.get("humidity_percent")),
        "status": payload.get("status", "UNKNOWN"),
        "error": payload.get("error"),
        "timestamp": payload.get("timestamp"),
        "published_at": payload.get("published_at"),
        "raw": payload,
    }


def relay_state_to_bool(value):
    return str(value).upper() == "ON"


def bool_to_relay_state(value):
    return "ON" if bool(value) else "OFF"
