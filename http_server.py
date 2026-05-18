import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import state

from auth import create_jwt, decode_jwt, verify_password
from config import HOST, PORT, RELAY_NAME_TO_ID, JWT_EXPIRY_SECONDS
from database import (
    get_user_by_email,
    get_user_by_id,
    list_users,
    create_user,
    update_user_status,
    delete_user,
    db_list_readings,
    db_list_readings_for_period,
)
from readings import latest_status
from relays import (
    get_android_relay_response,
    publish_relay_bool,
    publish_relay_desired,
    request_all_relay_status,
)
from utils import iso_now, log_event


PUBLIC_ENDPOINTS = {
    ("POST", "/api/auth/login"),
}


class Handler(BaseHTTPRequestHandler):
    current_user = None

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_common_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if not self.require_auth("GET", path):
            return

        log_event(f"HTTP GET {self.path}")

        if path == "/api/connect":
            self.write_json(
                {
                    "success": True,
                    "message": "Backend connection successful. Ready to transmit solar data.",
                    "timestamp": iso_now(),
                    "bind_host": HOST,
                    "port": PORT,
                    "authenticated_as": self.current_user["email"],
                }
            )

        elif path in ["/api/status", "/api/readings/latest"]:
            self.write_json(latest_status())

        elif path == "/api/readings/history":
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                self.write_json(
                    {
                        "success": False,
                        "message": "Invalid limit. Use a number between 1 and 1000.",
                    },
                    status=400,
                )
                return

            period = query.get("period", query.get("range", [None]))[0]

            if period:
                readings = db_list_readings_for_period(period, limit=limit)

                if readings is None:
                    self.write_json(
                        {
                            "success": False,
                            "message": "Invalid period. Use minute, hour, day, week, or month.",
                        },
                        status=400,
                    )
                    return

                self.write_json(readings)
                return

            self.write_json(db_list_readings(limit))

        elif path == "/api/inverters/main":
            with state.state_lock:
                self.write_json(state.inverters.get("must_1") or {})

        elif path == "/api/inverters/water":
            with state.state_lock:
                self.write_json(state.inverters.get("must_2") or {})

        elif path == "/api/inverters/status":
            with state.state_lock:
                self.write_json(
                    {
                        "main_inverter": state.inverters.get("must_1"),
                        "water_inverter": state.inverters.get("must_2"),
                        "mapping": {
                            "must_1": "USB0 main solar inverter",
                            "must_2": "USB1 water inverter",
                        },
                    }
                )

        elif path in ["/api/relays", "/api/relays/status"]:
            request_all_relay_status()
            self.write_json(get_android_relay_response())

        elif path == "/api/utility/status":
            with state.state_lock:
                self.write_json(state.utility_states.copy())

        elif path == "/api/alerts":
            with state.state_lock:
                self.write_json(state.alerts[-100:])

        elif path == "/api/errors/recent":
            with state.state_lock:
                self.write_json(state.errors[-100:])

        elif path == "/api/config":
            with state.state_lock:
                self.write_json(state.config.copy())

        elif path == "/api/system/status":
            with state.state_lock:
                self.write_json(
                    {
                        "backend_online": True,
                        "mqtt_connected": state.mqtt_client is not None,
                        "last_seen_mqtt": state.last_seen_mqtt,
                        "gateway_status": state.gateway.get("status"),
                        "gateway_last_seen": state.gateway.get("last_seen"),
                        "gateway_site_id": state.gateway.get("site_id"),
                        "gateway": state.gateway,
                        "has_main_inverter_data": state.inverters.get("must_1") is not None,
                        "has_water_inverter_data": state.inverters.get("must_2") is not None,
                        "has_dht11_data": state.sensors.get("dht11_1") is not None,
                    }
                )

        elif path == "/api/auth/me":
            self.write_json(
                {
                    "authenticated": True,
                    "user": self.safe_user(self.current_user),
                }
            )

        elif path == "/api/admin/users":
            if not self.require_admin():
                return

            self.write_json(
                {
                    "success": True,
                    "users": list_users(),
                }
            )

        else:
            self.write_json({"error": "Not found", "path": path}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_json()

        if path == "/api/auth/login":
            self.handle_login(body)
            return

        if not self.require_auth("POST", path):
            return

        log_event(f"HTTP POST {self.path} BODY {json.dumps(body)}")

        if path == "/api/override/readings":
            if body.get("enabled") is False or body.get("clear") is True:
                with state.state_lock:
                    state.manual_override = {
                        "enabled": False,
                        "battery_voltage": None,
                        "battery_temperature": None,
                        "ambient_temperature": None,
                        "updated_at": iso_now(),
                        "updated_by": self.current_user["email"],
                    }

                self.write_json(
                    {
                        "success": True,
                        "message": "Manual readings override disabled",
                        "override": state.manual_override,
                        "analytics": latest_status(),
                    }
                )
                return

            override_fields = [
                "battery_voltage",
                "battery_temperature",
                "ambient_temperature",
            ]

            if not any(field in body for field in override_fields):
                self.write_json(
                    {
                        "success": False,
                        "message": "Provide battery_voltage, battery_temperature, or ambient_temperature.",
                    },
                    status=400,
                )
                return

            parsed_values = {}

            for field in override_fields:
                if field not in body:
                    continue

                try:
                    parsed_values[field] = float(body[field])
                except (TypeError, ValueError):
                    self.write_json(
                        {
                            "success": False,
                            "message": f"Invalid {field}. Use a number.",
                        },
                        status=400,
                    )
                    return

            with state.state_lock:
                state.manual_override.update(parsed_values)
                state.manual_override["enabled"] = True
                state.manual_override["updated_at"] = iso_now()
                state.manual_override["updated_by"] = self.current_user["email"]
                override = state.manual_override.copy()

            self.write_json(
                {
                    "success": True,
                    "message": "Manual readings override enabled",
                    "override": override,
                    "analytics": latest_status(),
                }
            )

        elif path == "/api/relays/command":
            target = body.get("target", "")
            action = body.get("action", "OFF").upper()
            source = body.get("source", "android_app")

            success, message, data = publish_relay_desired(target, action, source=source)

            if not success:
                self.write_json({"success": False, "message": message}, status=400)
                return

            self.write_json(
                {
                    "success": True,
                    "message": message,
                    **data,
                    "analytics": latest_status(),
                }
            )

        elif path == "/api/relays":
            commands_sent = []

            for relay_name, value in body.items():
                if relay_name not in RELAY_NAME_TO_ID:
                    continue

                success, message, data = publish_relay_bool(
                    relay_name,
                    value,
                    source="android_app",
                )

                if success and data:
                    commands_sent.append(data)

            self.write_json(
                {
                    "success": True,
                    "message": "Relay commands sent",
                    "commands_sent": commands_sent,
                    "analytics": latest_status(),
                }
            )

        elif path.startswith("/api/relays/"):
            relay_name = path.strip("/").split("/")[-1]

            if relay_name not in RELAY_NAME_TO_ID:
                self.write_json(
                    {
                        "success": False,
                        "message": "Unknown relay name",
                        "relay_name": relay_name,
                    },
                    status=400,
                )
                return

            desired_value = body.get("state")

            if desired_value is None:
                self.write_json(
                    {
                        "success": False,
                        "message": "Missing state field. Use true or false.",
                    },
                    status=400,
                )
                return

            success, message, data = publish_relay_bool(
                relay_name,
                desired_value,
                source="android_app",
            )

            if not success:
                self.write_json({"success": False, "message": message}, status=400)
                return

            self.write_json(
                {
                    "success": True,
                    "message": message,
                    **data,
                    "analytics": latest_status(),
                }
            )

        elif path.startswith("/api/alerts/") and path.endswith("/ack"):
            try:
                parts = path.strip("/").split("/")
                alert_id = int(parts[2])
            except Exception:
                self.write_json({"success": False, "message": "Invalid alert id"}, status=400)
                return

            with state.state_lock:
                for alert in state.alerts:
                    if alert["id"] == alert_id:
                        alert["acknowledged"] = True
                        self.write_json({"success": True, "message": "Alert acknowledged"})
                        return

            self.write_json({"success": False, "message": "Alert not found"}, status=404)

        elif path == "/api/maintenance/report":
            with state.state_lock:
                state.maintenance_reports.append({"timestamp": iso_now(), **body})

            self.write_json({"success": True, "message": "Maintenance report saved"})

        elif path == "/api/utility/status":
            with state.state_lock:
                if "city_electricity" in body:
                    state.utility_states["city_electricity"] = bool(body["city_electricity"])

                if "generator" in body:
                    state.utility_states["generator"] = bool(body["generator"])

                updated = state.utility_states.copy()

            self.write_json(
                {
                    "success": True,
                    "message": "Utility state updated",
                    "utility_states": updated,
                }
            )

        elif path == "/api/admin/users":
            if not self.require_admin():
                return

            email = body.get("email", "").strip().lower()
            password = body.get("password", "")
            role = body.get("role", "user")
            status = body.get("status", "active")

            if not email or not password:
                self.write_json(
                    {
                        "success": False,
                        "message": "email and password are required",
                    },
                    status=400,
                )
                return

            if role not in ["admin", "user"]:
                self.write_json(
                    {
                        "success": False,
                        "message": "Invalid role. Use admin or user.",
                    },
                    status=400,
                )
                return

            if status not in ["active", "paused", "disabled"]:
                self.write_json(
                    {
                        "success": False,
                        "message": "Invalid status. Use active, paused, or disabled.",
                    },
                    status=400,
                )
                return

            user, error = create_user(email, password, role, status)

            if error:
                self.write_json(
                    {
                        "success": False,
                        "message": error,
                    },
                    status=400,
                )
                return

            self.write_json(
                {
                    "success": True,
                    "message": "User created",
                    "user": user,
                }
            )

        elif path.startswith("/api/admin/users/") and path.endswith("/pause"):
            if not self.require_admin():
                return

            user_id = self.extract_user_id_from_admin_path(path)
            success, message = update_user_status(user_id, "paused")

            self.write_json(
                {
                    "success": success,
                    "message": message,
                },
                status=200 if success else 400,
            )

        elif path.startswith("/api/admin/users/") and path.endswith("/activate"):
            if not self.require_admin():
                return

            user_id = self.extract_user_id_from_admin_path(path)
            success, message = update_user_status(user_id, "active")

            self.write_json(
                {
                    "success": success,
                    "message": message,
                },
                status=200 if success else 400,
            )

        elif path.startswith("/api/admin/users/") and path.endswith("/disable"):
            if not self.require_admin():
                return

            user_id = self.extract_user_id_from_admin_path(path)
            success, message = update_user_status(user_id, "disabled")

            self.write_json(
                {
                    "success": success,
                    "message": message,
                },
                status=200 if success else 400,
            )

        else:
            self.write_json({"error": "Not found", "path": path}, status=404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if not self.require_auth("DELETE", path):
            return

        if path.startswith("/api/admin/users/"):
            if not self.require_admin():
                return

            user_id = self.extract_user_id_from_admin_path(path)

            if user_id == self.current_user["id"]:
                self.write_json(
                    {
                        "success": False,
                        "message": "You cannot delete your own account while logged in",
                    },
                    status=400,
                )
                return

            success, message = delete_user(user_id)

            self.write_json(
                {
                    "success": success,
                    "message": message,
                },
                status=200 if success else 400,
            )

        else:
            self.write_json({"error": "Not found", "path": path}, status=404)

    def handle_login(self, body):
        email = body.get("email", "").strip().lower()
        password = body.get("password", "")

        if not email or not password:
            self.write_json(
                {
                    "success": False,
                    "message": "email and password are required",
                },
                status=400,
            )
            return

        user = get_user_by_email(email)

        if not user:
            self.write_json(
                {
                    "success": False,
                    "message": "Invalid email or password",
                },
                status=401,
            )
            return

        if user["status"] != "active":
            self.write_json(
                {
                    "success": False,
                    "message": f"Account is {user['status']}",
                },
                status=403,
            )
            return

        if not verify_password(password, user["password_hash"]):
            self.write_json(
                {
                    "success": False,
                    "message": "Invalid email or password",
                },
                status=401,
            )
            return

        token = create_jwt(user)

        self.write_json(
            {
                "success": True,
                "message": "Login successful",
                "token_type": "Bearer",
                "access_token": token,
                "expires_in_seconds": JWT_EXPIRY_SECONDS,
                "user": self.safe_user(user),
            }
        )

    def require_auth(self, method, path):
        if (method, path) in PUBLIC_ENDPOINTS:
            return True

        auth_header = self.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            self.write_json(
                {
                    "success": False,
                    "message": "Missing Authorization header. Use: Bearer token",
                },
                status=401,
            )
            return False

        token = auth_header.replace("Bearer ", "", 1).strip()
        payload, error = decode_jwt(token)

        if error:
            self.write_json(
                {
                    "success": False,
                    "message": error,
                },
                status=401,
            )
            return False

        user = get_user_by_id(payload.get("user_id"))

        if not user:
            self.write_json(
                {
                    "success": False,
                    "message": "User no longer exists",
                },
                status=401,
            )
            return False

        if user["status"] != "active":
            self.write_json(
                {
                    "success": False,
                    "message": f"Account is {user['status']}",
                },
                status=403,
            )
            return False

        self.current_user = user
        return True

    def require_admin(self):
        if not self.current_user or self.current_user.get("role") != "admin":
            self.write_json(
                {
                    "success": False,
                    "message": "Admin access required",
                },
                status=403,
            )
            return False

        return True

    def extract_user_id_from_admin_path(self, path):
        try:
            parts = path.strip("/").split("/")
            return int(parts[3])
        except Exception:
            return -1

    def safe_user(self, user):
        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "status": user["status"],
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
        }

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))

        if length == 0:
            return {}

        raw = self.rfile.read(length).decode("utf-8")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def write_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_common_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_common_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")

    def log_message(self, fmt, *args):
        log_event(f"{self.address_string()} - {fmt % args}")
