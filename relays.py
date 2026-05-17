import json

import state

from config import SITE_ID, RELAY_NAME_TO_ID, RELAY_ID_TO_NAME
from database import db_insert_relay_action
from normalizers import bool_to_relay_state, relay_state_to_bool
from utils import iso_now, log_event


def publish_mqtt(topic, payload, retain=False):
    if state.mqtt_client is None:
        return False

    try:
        state.mqtt_client.publish(topic, json.dumps(payload), qos=1, retain=retain)
        log_event(f"MQTT publish {topic}: {json.dumps(payload)} retain={retain}")
        return True
    except Exception as exc:
        log_event(f"MQTT publish failed for {topic}: {exc}")
        return False


def sync_android_relay_states_from_raw_relays():
    for relay_id, relay_data in state.relays.items():
        relay_name = RELAY_ID_TO_NAME.get(relay_id)

        if not relay_name:
            continue

        actual_state = relay_data.get("actual_state", "OFF")
        state.relay_states[relay_name] = relay_state_to_bool(actual_state)


def publish_relay_desired(relay_name, desired_state, source="android_app"):
    if relay_name not in RELAY_NAME_TO_ID:
        return False, "Unknown relay name", None

    relay_id = RELAY_NAME_TO_ID[relay_name]
    desired_state = str(desired_state).upper()

    if desired_state not in ["ON", "OFF"]:
        return False, "Invalid relay state", None

    topic = f"solar/{SITE_ID}/relay/{relay_id}/desired"

    command = {
        "state": desired_state,
    }

    with state.state_lock:
        state.relays[relay_id]["desired_state"] = desired_state
        state.relays[relay_id]["timestamp"] = iso_now()
        state.relay_states[relay_name] = desired_state == "ON"

    db_insert_relay_action(
        relay_id=relay_id,
        relay_name=relay_name,
        desired_state=desired_state,
        actual_state=None,
        applied=None,
        command_source=source,
    )

    publish_mqtt(topic, command, retain=False)

    return True, "Relay command sent", {
        "relay_name": relay_name,
        "relay_id": relay_id,
        "desired_state": desired_state,
    }


def publish_relay_bool(relay_name, value, source="android_app"):
    return publish_relay_desired(relay_name, bool_to_relay_state(value), source=source)


def request_all_relay_status():
    topic = f"solar/{SITE_ID}/relay/all/get"
    return publish_mqtt(topic, {}, retain=False)


def request_one_relay_status(relay_id):
    topic = f"solar/{SITE_ID}/relay/{relay_id}/get"
    return publish_mqtt(topic, {}, retain=False)


def get_android_relay_response():
    with state.state_lock:
        sync_android_relay_states_from_raw_relays()

        raw_relays = {
            relay_id: relay_data.get("actual_state", "UNKNOWN")
            for relay_id, relay_data in state.relays.items()
        }

        return {
            "relay_states": state.relay_states.copy(),
            "raw_relays": raw_relays,
            "relay_details": state.relays.copy(),
        }
