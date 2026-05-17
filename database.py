import json
import sqlite3
from datetime import datetime, timedelta

from auth import hash_password
from config import DB_FILE, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
from utils import iso_now, log_event


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS latest_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mqtt_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inverter_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                role TEXT,
                status TEXT,
                system_status TEXT,
                battery_voltage REAL,
                pv_voltage REAL,
                pv_current REAL,
                pv_power REAL,
                ac_output_voltage REAL,
                ac_output_frequency REAL,
                grid_voltage REAL,
                grid_frequency REAL,
                load_percent REAL,
                load_power_w REAL,
                load_current REAL,
                inverter_temperature_c REAL,
                work_state TEXT,
                raw_json TEXT,
                timestamp TEXT,
                received_at TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                temperature_c REAL,
                humidity_percent REAL,
                status TEXT,
                raw_json TEXT,
                timestamp TEXT,
                received_at TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS relay_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relay_id TEXT,
                relay_name TEXT,
                desired_state TEXT,
                actual_state TEXT,
                applied INTEGER,
                command_source TEXT,
                timestamp TEXT,
                confirmed_at TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                error TEXT,
                device_id TEXT,
                relay_id TEXT,
                topic TEXT,
                raw_json TEXT,
                timestamp TEXT,
                received_at TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
            """
        )

        conn.commit()

    seed_admin_user()


def row_to_dict(row):
    if row is None:
        return None

    return dict(row)


def seed_admin_user():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (DEFAULT_ADMIN_EMAIL,),
            ).fetchone()

            if existing:
                return

            now = iso_now()

            conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, role, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_ADMIN_EMAIL,
                    hash_password(DEFAULT_ADMIN_PASSWORD),
                    "admin",
                    "active",
                    now,
                    now,
                ),
            )

            conn.commit()
            log_event(f"Default admin user created: {DEFAULT_ADMIN_EMAIL}")

    except Exception as exc:
        log_event(f"Admin seed failed: {exc}")


def get_user_by_email(email):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                """
                SELECT id, email, password_hash, role, status, created_at, updated_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

            return row_to_dict(row)

    except Exception as exc:
        log_event(f"Get user by email failed: {exc}")
        return None


def get_user_by_id(user_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                """
                SELECT id, email, password_hash, role, status, created_at, updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

            return row_to_dict(row)

    except Exception as exc:
        log_event(f"Get user by id failed: {exc}")
        return None


def list_users():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """
                SELECT id, email, role, status, created_at, updated_at
                FROM users
                ORDER BY id ASC
                """
            ).fetchall()

            return [dict(row) for row in rows]

    except Exception as exc:
        log_event(f"List users failed: {exc}")
        return []


def create_user(email, password, role="user", status="active"):
    try:
        now = iso_now()

        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, role, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    hash_password(password),
                    role,
                    status,
                    now,
                    now,
                ),
            )

            conn.commit()

            return {
                "id": cur.lastrowid,
                "email": email,
                "role": role,
                "status": status,
                "created_at": now,
                "updated_at": now,
            }, None

    except sqlite3.IntegrityError:
        return None, "User email already exists"

    except Exception as exc:
        log_event(f"Create user failed: {exc}")
        return None, "Failed to create user"


def update_user_status(user_id, status):
    try:
        if status not in ["active", "paused", "disabled"]:
            return False, "Invalid status"

        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, iso_now(), user_id),
            )

            conn.commit()

            if cur.rowcount == 0:
                return False, "User not found"

            return True, "User status updated"

    except Exception as exc:
        log_event(f"Update user status failed: {exc}")
        return False, "Failed to update user status"


def delete_user(user_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute(
                "DELETE FROM users WHERE id = ?",
                (user_id,),
            )

            conn.commit()

            if cur.rowcount == 0:
                return False, "User not found"

            return True, "User deleted"

    except Exception as exc:
        log_event(f"Delete user failed: {exc}")
        return False, "Failed to delete user"


def db_upsert_latest_state(key, value):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO latest_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), iso_now()),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB latest_state upsert failed: {exc}")


def db_insert_mqtt(topic, payload):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "INSERT INTO mqtt_messages (timestamp, topic, payload) VALUES (?, ?, ?)",
                (iso_now(), topic, json.dumps(payload)),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB mqtt insert failed: {exc}")


def db_insert_reading(reading):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "INSERT INTO readings (timestamp, payload) VALUES (?, ?)",
                (reading["timestamp"], json.dumps(reading)),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB reading insert failed: {exc}")


def db_list_readings(limit=100):
    try:
        limit = max(1, min(int(limit), 1000))

        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """
                SELECT id, timestamp, payload
                FROM readings
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        readings = []

        for row in reversed(rows):
            try:
                item = json.loads(row["payload"])
            except Exception:
                item = {"payload": row["payload"]}

            item.setdefault("id", row["id"])
            item.setdefault("timestamp", row["timestamp"])
            readings.append(item)

        return readings

    except Exception as exc:
        log_event(f"DB readings list failed: {exc}")
        return []


def db_list_readings_for_period(period, limit=1000):
    period_seconds = {
        "minute": 60,
        "minutes": 60,
        "hour": 60 * 60,
        "hours": 60 * 60,
        "day": 60 * 60 * 24,
        "days": 60 * 60 * 24,
        "week": 60 * 60 * 24 * 7,
        "weeks": 60 * 60 * 24 * 7,
        "wee": 60 * 60 * 24 * 7,
        "month": 60 * 60 * 24 * 30,
        "months": 60 * 60 * 24 * 30,
    }

    normalized_period = str(period or "").strip().lower()

    if normalized_period not in period_seconds:
        return None

    try:
        limit = max(1, min(int(limit), 5000))
        since = datetime.now() - timedelta(seconds=period_seconds[normalized_period])
        since_text = since.strftime("%Y-%m-%dT%H:%M:%S")

        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """
                SELECT id, timestamp, payload
                FROM readings
                WHERE timestamp >= ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (since_text, limit),
            ).fetchall()

        if not rows:
            return -1

        readings = []

        for row in rows:
            try:
                item = json.loads(row["payload"])
            except Exception:
                item = {"payload": row["payload"]}

            item.setdefault("id", row["id"])
            item.setdefault("timestamp", row["timestamp"])
            readings.append(item)

        return readings

    except Exception as exc:
        log_event(f"DB readings period list failed: {exc}")
        return -1


def db_insert_inverter_reading(item):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO inverter_readings (
                    device_id, role, status, system_status,
                    battery_voltage, pv_voltage, pv_current, pv_power,
                    ac_output_voltage, ac_output_frequency,
                    grid_voltage, grid_frequency,
                    load_percent, load_power_w, load_current,
                    inverter_temperature_c, work_state,
                    raw_json, timestamp, received_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("device_id"),
                    item.get("role"),
                    item.get("status"),
                    item.get("system_status"),
                    item.get("battery_voltage"),
                    item.get("pv_voltage"),
                    item.get("pv_current"),
                    item.get("pv_power"),
                    item.get("ac_output_voltage"),
                    item.get("ac_output_frequency"),
                    item.get("grid_voltage"),
                    item.get("grid_frequency"),
                    item.get("load_percent"),
                    item.get("load_power_w"),
                    item.get("load_current"),
                    item.get("inverter_temperature_c"),
                    item.get("work_state"),
                    json.dumps(item.get("raw", item)),
                    item.get("timestamp"),
                    iso_now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB inverter insert failed: {exc}")


def db_insert_sensor_reading(item):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO sensor_readings (
                    device_id, temperature_c, humidity_percent,
                    status, raw_json, timestamp, received_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("device_id"),
                    item.get("temperature_c"),
                    item.get("humidity_percent"),
                    item.get("status"),
                    json.dumps(item.get("raw", item)),
                    item.get("timestamp"),
                    iso_now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB sensor insert failed: {exc}")


def db_insert_relay_action(relay_id, relay_name, desired_state, actual_state, applied, command_source):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO relay_actions (
                    relay_id, relay_name, desired_state, actual_state,
                    applied, command_source, timestamp, confirmed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relay_id,
                    relay_name,
                    desired_state,
                    actual_state,
                    1 if applied else 0 if applied is not None else None,
                    command_source,
                    iso_now(),
                    iso_now() if applied else None,
                ),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB relay action insert failed: {exc}")


def db_insert_system_error(topic, payload):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO system_errors (
                    source, error, device_id, relay_id, topic,
                    raw_json, timestamp, received_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("source"),
                    payload.get("error"),
                    payload.get("device_id"),
                    payload.get("relay_id"),
                    topic,
                    json.dumps(payload),
                    payload.get("timestamp"),
                    iso_now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB system error insert failed: {exc}")


def db_insert_alert(alert):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO alerts (timestamp, alert_type, severity, message, acknowledged)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    alert["timestamp"],
                    alert["alert_type"],
                    alert["severity"],
                    alert["message"],
                    1 if alert.get("acknowledged") else 0,
                ),
            )
            conn.commit()
    except Exception as exc:
        log_event(f"DB alert insert failed: {exc}")
