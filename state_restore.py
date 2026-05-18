import state

from config import RELAY_ID_TO_NAME
from database import db_list_latest_state
from normalizers import relay_state_to_bool
from relays import relay_state_to_logical_bool
from utils import log_event


def restore_latest_state_from_db():
    latest_items = db_list_latest_state()

    if not latest_items:
        log_event("No latest state found in SQLite to restore")
        return

    restored = []
    last_seen_mqtt = None

    with state.state_lock:
        gateway_item = latest_items.get("gateway")

        if gateway_item:
            state.gateway = gateway_item["value"]
            last_seen_mqtt = _newer_timestamp(
                last_seen_mqtt,
                state.gateway.get("received_at") or gateway_item.get("updated_at"),
            )
            restored.append("gateway")

        for key, item in latest_items.items():
            value = item["value"]

            if key.startswith("sensor_"):
                device_id = key.replace("sensor_", "", 1)
                state.sensors[device_id] = value
                last_seen_mqtt = _newer_timestamp(
                    last_seen_mqtt,
                    value.get("received_at") or item.get("updated_at"),
                )
                restored.append(key)

            elif key.startswith("inverter_"):
                device_id = key.replace("inverter_", "", 1)
                state.inverters[device_id] = value
                last_seen_mqtt = _newer_timestamp(
                    last_seen_mqtt,
                    value.get("received_at") or item.get("updated_at"),
                )
                restored.append(key)

            elif key.startswith("relay_"):
                relay_id = key.replace("relay_", "", 1)
                state.relays[relay_id] = value

                relay_name = RELAY_ID_TO_NAME.get(relay_id)

                if relay_name:
                    relay_state = value.get("desired_state") or value.get("actual_state", "OFF")
                    state.relay_states[relay_name] = relay_state_to_logical_bool(
                        relay_name,
                        relay_state,
                    )
                else:
                    state.relay_states[relay_id] = relay_state_to_bool(value.get("actual_state"))

                last_seen_mqtt = _newer_timestamp(
                    last_seen_mqtt,
                    value.get("received_at") or item.get("updated_at"),
                )
                restored.append(key)

        if last_seen_mqtt:
            state.last_seen_mqtt = last_seen_mqtt

    log_event(f"Restored latest state from SQLite: {', '.join(restored)}")


def _newer_timestamp(current, candidate):
    if not candidate:
        return current

    if not current:
        return candidate

    return candidate if str(candidate) > str(current) else current
