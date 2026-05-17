import json

import state

from readings import latest_status
from relays import publish_relay_desired, request_all_relay_status
from utils import log_event


def cli_loop():
    while state.running:
        print("\nSolar backend CLI")
        print("1. Show latest full status")
        print("2. Show main inverter / must_1 / USB0")
        print("3. Show water inverter / must_2 / USB1")
        print("4. Show DHT11")
        print("5. Show relay states")
        print("6. Request all relay statuses")
        print("7. Edit technician phone")
        print("8. Turn relay ON/OFF")
        print("9. Show gateway status")
        print("10. Show recent errors")

        try:
            choice = input("Choice: ").strip()
        except EOFError:
            break

        if choice == "1":
            print(json.dumps(latest_status(), indent=2))

        elif choice == "2":
            with state.state_lock:
                print(json.dumps(state.inverters.get("must_1"), indent=2))

        elif choice == "3":
            with state.state_lock:
                print(json.dumps(state.inverters.get("must_2"), indent=2))

        elif choice == "4":
            with state.state_lock:
                print(json.dumps(state.sensors.get("dht11_1"), indent=2))

        elif choice == "5":
            with state.state_lock:
                print(json.dumps(state.relays, indent=2))
                print(json.dumps(state.relay_states, indent=2))

        elif choice == "6":
            request_all_relay_status()
            print("Relay status request sent.")

        elif choice == "7":
            phone = input("Technician phone: ").strip()

            with state.state_lock:
                state.config["technician_phone"] = phone

            log_event(f"CLI changed technician phone to {phone}")

        elif choice == "8":
            print("Available relays:")
            print("- water_heater")
            print("- water_pump")
            print("- reverse_osmosis")

            relay_name = input("Relay name: ").strip()
            action = input("Action ON/OFF: ").strip().upper()

            success, message, data = publish_relay_desired(
                relay_name,
                action,
                source="server_cli",
            )

            print(
                json.dumps(
                    {
                        "success": success,
                        "message": message,
                        "data": data,
                    },
                    indent=2,
                )
            )

        elif choice == "9":
            with state.state_lock:
                print(json.dumps(state.gateway, indent=2))

        elif choice == "10":
            with state.state_lock:
                print(json.dumps(state.errors[-20:], indent=2))

        else:
            print("Unknown choice")
