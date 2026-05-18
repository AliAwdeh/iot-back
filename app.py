#!/usr/bin/env python3

import signal
import sys
import threading
from http.server import ThreadingHTTPServer

import state

from cli import cli_loop
from config import HOST, PORT, MQTT_BROKER, MQTT_PORT
from database import init_db
from http_server import Handler
from mqtt_service import init_mqtt, stop_mqtt
from readings import latest_status
from state_restore import restore_latest_state_from_db
from utils import log_event


def shutdown_handler(signum, frame):
    state.running = False

    log_event("Backend shutting down")

    stop_mqtt()

    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    init_db()
    restore_latest_state_from_db()
    init_mqtt()

    latest_status()

    server = ThreadingHTTPServer((HOST, PORT), Handler)

    threading.Thread(target=cli_loop, daemon=True).start()

    log_event(f"Solar backend listening on http://{HOST}:{PORT}/api")
    log_event(f"MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    log_event("HTTP app flow: Android -> backend")
    log_event("MQTT flow: Raspberry Pi -> broker -> backend")
    log_event("Relay command flow: backend -> broker -> Raspberry Pi -> Pico")
    log_event("Main inverter data source: must_1 / USB0")
    log_event("Water inverter data source: must_2 / USB1")
    log_event("Subscribed topic: solar/site1/#")

    server.serve_forever()


if __name__ == "__main__":
    main()
