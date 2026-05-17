import json

import state

from config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    MQTT_ENABLED,
    SITE_ID,
    RELAY_ID_TO_NAME,
)
from database import (
    db_insert_mqtt,
    db_insert_inverter_reading,
    db_insert_sensor_reading,
    db_insert_system_error,
    db_upsert_latest_state,
)
from normalizers import normalize_dht11_payload, normalize_inverter_payload
from relays import sync_android_relay_states_from_raw_relays
from utils import iso_now, log_event


def handle_gateway_status(payload):
    received_at = iso_now()

    with state.state_lock:
        state.gateway = {
            "status": payload.get("status", "unknown"),
            "last_seen": payload.get("timestamp") or payload.get("published_at") or iso_now(),
            "received_at": received_at,
            "site_id": payload.get("site_id"),
            "raw": payload,
        }

        state.last_seen_mqtt = received_at

    db_upsert_latest_state("gateway", state.gateway)
    log_event(f"Gateway status updated: {state.gateway['status']}")


def handle_system_error(topic, payload):
    error_item = {
        "source": payload.get("source"),
        "status": payload.get("status"),
        "error": payload.get("error"),
        "device_id": payload.get("device_id"),
        "relay_id": payload.get("relay_id"),
        "port": payload.get("port"),
        "topic": topic,
        "payload": payload,
        "timestamp": payload.get("timestamp") or iso_now(),
        "published_at": payload.get("published_at"),
    }

    with state.state_lock:
        state.errors.append(error_item)

        if len(state.errors) > 100:
            state.errors.pop(0)

        state.last_seen_mqtt = iso_now()

    db_insert_system_error(topic, payload)
    log_event(f"System error received: {json.dumps(error_item)}")


def handle_sensor_telemetry(topic, payload):
    sensor = normalize_dht11_payload(payload)
    device_id = sensor.get("device_id", "dht11_1")
    received_at = iso_now()
    sensor["received_at"] = received_at

    with state.state_lock:
        if sensor.get("status") == "ok":
            state.sensors[device_id] = sensor
            db_upsert_latest_state(f"sensor_{device_id}", sensor)
        else:
            state.errors.append(
                {
                    "source": "dht11",
                    "status": sensor.get("status"),
                    "error": sensor.get("error"),
                    "device_id": device_id,
                    "topic": topic,
                    "payload": payload,
                    "timestamp": sensor.get("timestamp") or iso_now(),
                    "published_at": sensor.get("published_at"),
                }
            )

        state.last_seen_mqtt = received_at

    db_insert_sensor_reading(sensor)
    log_event(f"Sensor telemetry updated: {device_id}")


def handle_inverter_telemetry(topic, payload):
    inverter = normalize_inverter_payload(payload)
    device_id = inverter.get("device_id")
    received_at = iso_now()

    if not device_id:
        log_event(f"Inverter telemetry missing device_id: {json.dumps(payload)}")
        return

    inverter["received_at"] = received_at

    with state.state_lock:
        state.inverters[device_id] = inverter
        state.last_seen_mqtt = received_at

    db_upsert_latest_state(f"inverter_{device_id}", inverter)
    db_insert_inverter_reading(inverter)

    log_event(f"Inverter telemetry updated: {device_id}")


def handle_one_relay_status(topic, payload):
    relay_id = payload.get("relay_id")

    if not relay_id:
        parts = topic.split("/")
        try:
            relay_id = parts[3]
        except Exception:
            relay_id = None

    if not relay_id:
        log_event(f"Relay status missing relay_id: {json.dumps(payload)}")
        return

    actual_state = payload.get("actual_state") or payload.get("state") or "UNKNOWN"
    desired_state = payload.get("desired_state")
    applied = payload.get("applied")

    received_at = iso_now()

    relay_data = {
        "actual_state": str(actual_state).upper(),
        "desired_state": str(desired_state).upper() if desired_state else None,
        "applied": applied,
        "source": payload.get("source"),
        "timestamp": payload.get("timestamp") or iso_now(),
        "published_at": payload.get("published_at"),
        "received_at": received_at,
        "raw": payload,
    }

    with state.state_lock:
        state.relays[relay_id] = relay_data
        sync_android_relay_states_from_raw_relays()
        state.last_seen_mqtt = received_at

    db_upsert_latest_state(f"relay_{relay_id}", relay_data)

    relay_name = RELAY_ID_TO_NAME.get(relay_id, relay_id)
    log_event(f"Relay status updated: {relay_name}={relay_data['actual_state']}")


def handle_all_relay_status(payload):
    relays = payload.get("relays", {})
    received_at = iso_now()

    with state.state_lock:
        for relay_id, actual_state in relays.items():
            current = state.relays.get(relay_id, {})

            state.relays[relay_id] = {
                "actual_state": str(actual_state).upper(),
                "desired_state": current.get("desired_state"),
                "applied": current.get("applied"),
                "source": payload.get("source"),
                "timestamp": payload.get("timestamp") or iso_now(),
                "published_at": payload.get("published_at"),
                "received_at": received_at,
                "raw": payload,
            }

            db_upsert_latest_state(f"relay_{relay_id}", state.relays[relay_id])

        sync_android_relay_states_from_raw_relays()
        state.last_seen_mqtt = received_at

    log_event("All relay statuses updated")


def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        log_event(f"MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")

        topic = f"solar/{SITE_ID}/#"
        client.subscribe(topic, qos=1)
        log_event(f"MQTT subscribed to {topic}")

        client.publish(f"solar/{SITE_ID}/relay/all/get", json.dumps({}), qos=1, retain=False)
        log_event("Requested all relay statuses on startup")

    else:
        log_event(f"MQTT connection failed with code {rc}")


def on_mqtt_message(client, userdata, msg):
    topic = msg.topic
    raw = msg.payload.decode("utf-8", errors="ignore")

    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {
            "raw_payload": raw,
            "parse_error": True,
        }

    log_event(f"MQTT receive {topic}: {json.dumps(payload)}")
    db_insert_mqtt(topic, payload)

    try:
        if topic == f"solar/{SITE_ID}/system/status":
            handle_gateway_status(payload)

        elif topic == f"solar/{SITE_ID}/system/errors":
            handle_system_error(topic, payload)

        elif topic == f"solar/{SITE_ID}/relay/all/status":
            handle_all_relay_status(payload)

        elif topic.startswith(f"solar/{SITE_ID}/sensor/") and topic.endswith("/telemetry"):
            handle_sensor_telemetry(topic, payload)

        elif topic.startswith(f"solar/{SITE_ID}/inverter/") and topic.endswith("/telemetry"):
            handle_inverter_telemetry(topic, payload)

        elif topic.startswith(f"solar/{SITE_ID}/relay/") and topic.endswith("/status"):
            handle_one_relay_status(topic, payload)

    except Exception as exc:
        log_event(f"MQTT message handler error for {topic}: {exc}")


def init_mqtt():
    if not MQTT_ENABLED:
        return

    try:
        import paho.mqtt.client as mqtt

        try:
            state.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except Exception:
            state.mqtt_client = mqtt.Client()

        if MQTT_USERNAME:
            state.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        state.mqtt_client.on_connect = on_mqtt_connect
        state.mqtt_client.on_message = on_mqtt_message

        state.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        state.mqtt_client.loop_start()

    except Exception as exc:
        state.mqtt_client = None
        log_event(f"MQTT disabled for this run: {exc}")
        log_event("Install MQTT support with: pip install paho-mqtt")


def stop_mqtt():
    try:
        if state.mqtt_client is not None:
            state.mqtt_client.loop_stop()
            state.mqtt_client.disconnect()
    except Exception:
        pass
