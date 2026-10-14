import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR", os.path.join(os.path.dirname(BASE_DIR), "frontend")
)

app = Flask(__name__)
CORS(app)
init_db()


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ──────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────

def hash_password(password):
    # PBKDF2 works on every Python build. Werkzeug's default (scrypt) is
    # missing on some, such as the Python 3.9 that ships with macOS.
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(stored, password):
    """Check a password against its stored hash.

    Accounts created by older versions of the app stored an unsalted SHA-256
    hex digest. Those are still accepted so existing users can log in, and
    login() upgrades them to a salted hash on the next successful sign-in.
    """
    if stored.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored, password)
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(stored, legacy)


def is_legacy_hash(stored):
    return not stored.startswith(("pbkdf2:", "scrypt:"))


def get_company_from_token(token):
    if not token:
        return None
    conn = get_db()
    company = conn.execute("SELECT * FROM companies WHERE token=?", (token,)).fetchone()
    conn.close()
    return company


def auth_required():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return get_company_from_token(token)


def now_utc():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ──────────────────────────────────────────────
# AUDIT LOG HELPER
# ──────────────────────────────────────────────

def log_action(company_id, action, detail=""):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_log (company_id, action, detail, timestamp) VALUES (?, ?, ?, ?)",
            (company_id, action, detail, now_utc()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[audit log error] {e}")


# ──────────────────────────────────────────────
# AUTH ROUTES
# ──────────────────────────────────────────────

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"status": "error", "message": "All fields required"}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 400

    conn = get_db()
    existing = conn.execute("SELECT id FROM companies WHERE email=?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "Email already registered"}), 400

    token = secrets.token_hex(32)
    conn.execute(
        "INSERT INTO companies (name, email, password, token) VALUES (?,?,?,?)",
        (name, email, hash_password(password), token),
    )
    conn.commit()
    company = conn.execute("SELECT * FROM companies WHERE email=?", (email,)).fetchone()
    conn.close()
    return jsonify({"status": "success", "token": token, "company": {"id": company["id"], "name": company["name"], "email": company["email"]}})


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    conn = get_db()
    company = conn.execute("SELECT * FROM companies WHERE email=?", (email,)).fetchone()
    if not company or not verify_password(company["password"], password):
        conn.close()
        return jsonify({"status": "error", "message": "Invalid email or password"}), 401
    token = secrets.token_hex(32)
    if is_legacy_hash(company["password"]):
        conn.execute("UPDATE companies SET password=? WHERE id=?", (hash_password(password), company["id"]))
    conn.execute("UPDATE companies SET token=? WHERE id=?", (token, company["id"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "token": token, "company": {"id": company["id"], "name": company["name"], "email": company["email"]}})


@app.route("/logout", methods=["POST"])
def logout():
    company = auth_required()
    if company:
        conn = get_db()
        conn.execute("UPDATE companies SET token=NULL WHERE id=?", (company["id"],))
        conn.commit()
        conn.close()
    return jsonify({"status": "success"})


@app.route("/change-password", methods=["PUT"])
def change_password():
    """Change a password. Requires the current password.

    There is no email service in this project, so a true "forgot password"
    flow is not possible. Requiring the current password stops anyone from
    taking over an account by knowing only its email address.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    current = data.get("current_password", "")
    new = data.get("new_password", "")
    if not email or not current or not new:
        return jsonify({"status": "error", "message": "All fields required"}), 400
    if len(new) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 400

    conn = get_db()
    company = conn.execute("SELECT * FROM companies WHERE email=?", (email,)).fetchone()
    if not company or not verify_password(company["password"], current):
        conn.close()
        return jsonify({"status": "error", "message": "Invalid email or password"}), 401
    # Changing the password also signs out any existing sessions.
    conn.execute("UPDATE companies SET password=?, token=NULL WHERE id=?", (hash_password(new), company["id"]))
    conn.commit()
    conn.close()
    log_action(company["id"], "CHANGE_PASSWORD", "Password changed")
    return jsonify({"status": "success"})


@app.route("/me", methods=["GET"])
def me():
    company = auth_required()
    if not company:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    return jsonify({"company": {"id": company["id"], "name": company["name"], "email": company["email"], "open_time": company["open_time"], "close_time": company["close_time"]}})


# ──────────────────────────────────────────────
# COMPANY SETTINGS
# ──────────────────────────────────────────────

@app.route("/company", methods=["POST"])
def save_company():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE companies SET name=?, open_time=?, close_time=? WHERE id=?",
        (data["name"], data["open_time"], data["close_time"], company["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})


# ──────────────────────────────────────────────
# ROLES
# ──────────────────────────────────────────────

@app.route("/roles", methods=["GET"])
def get_roles():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    roles = conn.execute("SELECT * FROM roles WHERE company_id=?", (company["id"],)).fetchall()
    conn.close()
    return jsonify({"roles": [dict(r) for r in roles]})


@app.route("/roles", methods=["POST"])
def add_role():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    conn = get_db()
    existing = conn.execute("SELECT id FROM roles WHERE company_id=? AND name=?", (company["id"], data["name"])).fetchone()
    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "Role already exists"}), 400
    conn.execute("INSERT INTO roles (company_id, name) VALUES (?,?)", (company["id"], data["name"]))
    conn.commit()
    conn.close()
    log_action(company["id"], "ADD_ROLE", f"Added role: {data['name']}")
    return jsonify({"status": "success"})


@app.route("/roles/<int:role_id>", methods=["DELETE"])
def delete_role(role_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    role = conn.execute("SELECT name FROM roles WHERE id=? AND company_id=?", (role_id, company["id"])).fetchone()
    if not role:
        conn.close()
        return jsonify({"status": "error", "message": "Role not found"}), 404
    log_action(company["id"], "DELETE_ROLE", f"Deleted role: {role['name']}")
    conn.execute("DELETE FROM roles WHERE id=? AND company_id=?", (role_id, company["id"]))
    conn.execute("DELETE FROM worker_roles WHERE role_id=?", (role_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ──────────────────────────────────────────────
# WORKERS
# ──────────────────────────────────────────────

@app.route("/workers", methods=["GET"])
def get_workers():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    workers = conn.execute("SELECT * FROM workers WHERE company_id=?", (company["id"],)).fetchall()
    result = []
    for w in workers:
        availability = conn.execute("SELECT day FROM availability WHERE worker_id=?", (w["id"],)).fetchall()
        roles = conn.execute(
            "SELECT r.id, r.name FROM roles r JOIN worker_roles wr ON r.id = wr.role_id WHERE wr.worker_id=?",
            (w["id"],),
        ).fetchall()
        result.append({
            "id": w["id"], "name": w["name"], "max_hours": w["max_hours"],
            "overtime": w["overtime"], "notes": w["notes"] or "",
            "availability": [d["day"] for d in availability],
            "roles": [dict(r) for r in roles],
        })
    conn.close()
    return jsonify({"workers": result})


def _company_role_ids(conn, company_id, role_ids):
    """Keep only role IDs that belong to this company."""
    valid = []
    for role_id in role_ids:
        if conn.execute("SELECT 1 FROM roles WHERE id=? AND company_id=?", (role_id, company_id)).fetchone():
            valid.append(role_id)
    return valid


@app.route("/add-worker", methods=["POST"])
def add_worker():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO workers (company_id, name, max_hours, overtime, notes) VALUES (?,?,?,?,?)",
        (company["id"], data["name"], data["max_hours"], data["overtime"], data.get("notes", "")),
    )
    worker_id = cursor.lastrowid
    for day in data.get("availability", []):
        conn.execute("INSERT INTO availability (worker_id, day) VALUES (?,?)", (worker_id, day))
    for role_id in _company_role_ids(conn, company["id"], data.get("roles", [])):
        conn.execute("INSERT INTO worker_roles (worker_id, role_id) VALUES (?,?)", (worker_id, role_id))
    conn.commit()
    conn.close()
    log_action(company["id"], "ADD_WORKER", f"Added worker: {data['name']}")
    return jsonify({"status": "success"})


@app.route("/delete-worker/<int:worker_id>", methods=["DELETE"])
def delete_worker(worker_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    worker = conn.execute("SELECT id, name FROM workers WHERE id=? AND company_id=?", (worker_id, company["id"])).fetchone()
    if not worker:
        conn.close()
        return jsonify({"status": "error"}), 403
    log_action(company["id"], "DELETE_WORKER", f"Deleted worker: {worker['name']}")
    conn.execute("DELETE FROM availability WHERE worker_id=?", (worker_id,))
    conn.execute("DELETE FROM worker_roles WHERE worker_id=?", (worker_id,))
    conn.execute("DELETE FROM workers WHERE id=?", (worker_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


@app.route("/edit-worker/<int:worker_id>", methods=["PUT"])
def edit_worker(worker_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    conn = get_db()
    worker = conn.execute("SELECT * FROM workers WHERE id = ? AND company_id = ?", (worker_id, company["id"])).fetchone()
    if not worker:
        conn.close()
        return jsonify({"status": "error", "message": "Worker not found"}), 404
    data = request.json
    name = data.get("name", "").strip()
    max_hours = data.get("max_hours", 40)
    overtime = data.get("overtime", "no")
    notes = data.get("notes", worker["notes"] or "")
    availability = data.get("availability", [])
    role_ids = data.get("roles", [])
    if not name:
        conn.close()
        return jsonify({"status": "error", "message": "Name is required"}), 400
    conn.execute("UPDATE workers SET name=?, max_hours=?, overtime=?, notes=? WHERE id=?", (name, max_hours, overtime, notes, worker_id))
    conn.execute("DELETE FROM availability WHERE worker_id=?", (worker_id,))
    for day in availability:
        conn.execute("INSERT INTO availability (worker_id, day) VALUES (?,?)", (worker_id, day))
    conn.execute("DELETE FROM worker_roles WHERE worker_id=?", (worker_id,))
    for role_id in _company_role_ids(conn, company["id"], role_ids):
        conn.execute("INSERT INTO worker_roles (worker_id, role_id) VALUES (?,?)", (worker_id, role_id))
    conn.commit()
    conn.close()
    log_action(company["id"], "EDIT_WORKER", f"Edited worker: {name}")
    return jsonify({"status": "success", "message": "Worker updated"})


@app.route("/worker-note/<int:worker_id>", methods=["POST"])
def update_worker_note(worker_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    note = data.get("note", "")
    conn = get_db()
    worker = conn.execute("SELECT id FROM workers WHERE id=? AND company_id=?", (worker_id, company["id"])).fetchone()
    if not worker:
        conn.close()
        return jsonify({"status": "error"}), 403
    conn.execute("UPDATE workers SET notes=? WHERE id=?", (note, worker_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


# ──────────────────────────────────────────────
# SCHEDULE GENERATION
# ──────────────────────────────────────────────

def build_schedule(company, shifts, label, log_label):
    """Archive the current schedule, then fill each shift with eligible workers.

    The algorithm is greedy, in the order shifts are listed:
      * a worker is eligible if they are available that day and hold the role
      * a worker gets at most one shift per day
      * a worker cannot go past max_hours unless overtime is allowed
      * slots that cannot be filled are kept as blank rows so the manager
        can see the gap and assign someone by hand
    """
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) as cnt FROM schedule WHERE company_id=?", (company["id"],)).fetchone()
    if existing["cnt"] > 0:
        archive_id = conn.execute(
            "INSERT INTO schedule_history (company_id, label, created_at) VALUES (?,?,?)",
            (company["id"], label, now_utc()),
        ).lastrowid
        rows = conn.execute("SELECT * FROM schedule WHERE company_id=?", (company["id"],)).fetchall()
        for r in rows:
            conn.execute(
                "INSERT INTO schedule_history_shifts (history_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (archive_id, r["worker_id"], r["day"], r["start_time"], r["end_time"], r["role_id"]),
            )

    conn.execute("DELETE FROM schedule WHERE company_id=?", (company["id"],))
    workers = conn.execute("SELECT * FROM workers WHERE company_id=?", (company["id"],)).fetchall()
    hours_used = {w["id"]: 0 for w in workers}
    assigned_today = {w["id"]: set() for w in workers}
    assigned = []
    unassigned = []
    fmt = "%H:%M"

    for shift in shifts:
        day = shift["day"]
        start = shift["start_time"]
        end = shift["end_time"]
        role_id = shift["role_id"]
        needed = int(shift["workers_needed"])
        try:
            shift_hours = (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).seconds / 3600
        except (ValueError, TypeError):
            shift_hours = 8
        eligible = conn.execute("""
            SELECT w.* FROM workers w
            JOIN availability a ON w.id = a.worker_id
            JOIN worker_roles wr ON w.id = wr.worker_id
            WHERE a.day=? AND wr.role_id=? AND w.company_id=?
        """, (day, role_id, company["id"])).fetchall()
        count = 0
        for worker in eligible:
            if count >= needed:
                break
            wid = worker["id"]
            if day in assigned_today[wid]:
                continue
            projected = hours_used[wid] + shift_hours
            if projected > worker["max_hours"] and worker["overtime"] != "yes":
                continue
            conn.execute(
                "INSERT INTO schedule (company_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (company["id"], wid, day, start, end, role_id),
            )
            hours_used[wid] = projected
            assigned_today[wid].add(day)
            assigned.append({"worker": worker["name"], "day": day})
            count += 1
        for _ in range(needed - count):
            conn.execute(
                "INSERT INTO schedule (company_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (company["id"], None, day, start, end, role_id),
            )
            unassigned.append({"day": day, "start": start, "end": end, "role_id": role_id, "needed": needed, "filled": count})

    conn.commit()
    conn.close()
    log_action(company["id"], "GENERATE_SCHEDULE", f"{log_label}: {len(assigned)} assigned, {len(unassigned)} unfilled")
    return {"status": "success", "assigned": assigned, "unassigned": unassigned}


@app.route("/generate-schedule", methods=["POST"])
def generate_schedule():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    shifts = data.get("shifts", [])
    label = data.get("label", datetime.utcnow().strftime("Week of %b %d, %Y"))

    # Save the shift requirements so Refresh can replay them later
    conn = get_db()
    conn.execute("DELETE FROM last_shift_requirements WHERE company_id=?", (company["id"],))
    conn.execute(
        "INSERT INTO last_shift_requirements (company_id, shifts_json) VALUES (?,?)",
        (company["id"], json.dumps(shifts)),
    )
    conn.commit()
    conn.close()

    return jsonify(build_schedule(company, shifts, label, "Generated"))


@app.route("/refresh-schedule", methods=["POST"])
def refresh_schedule():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    row = conn.execute("SELECT shifts_json FROM last_shift_requirements WHERE company_id=?", (company["id"],)).fetchone()
    conn.close()
    if not row:
        return jsonify({"status": "error", "message": "No previous schedule found"}), 404
    saved = json.loads(row["shifts_json"])
    label = datetime.utcnow().strftime("Week of %b %d, %Y")
    return jsonify(build_schedule(company, saved, label, "Refreshed"))


# ──────────────────────────────────────────────
# SCHEDULE EDITING
# ──────────────────────────────────────────────

@app.route("/schedule", methods=["GET"])
def get_schedule():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    rows = conn.execute("""
        SELECT s.id, s.day, s.start_time, s.end_time, w.name as worker, w.id as worker_id, r.name as role, r.id as role_id
        FROM schedule s
        LEFT JOIN workers w ON s.worker_id = w.id
        LEFT JOIN roles r ON s.role_id = r.id
        WHERE s.company_id=?
        ORDER BY s.day, s.start_time
    """, (company["id"],)).fetchall()
    conn.close()
    return jsonify({"schedule": [dict(r) for r in rows]})


@app.route("/schedule/<int:shift_id>", methods=["PUT"])
def edit_shift(shift_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    conn = get_db()
    shift = conn.execute("SELECT * FROM schedule WHERE id=? AND company_id=?", (shift_id, company["id"])).fetchone()
    if not shift:
        conn.close()
        return jsonify({"status": "error", "message": "Shift not found"}), 404
    worker_id = data.get("worker_id", shift["worker_id"])
    start_time = data.get("start_time", shift["start_time"])
    end_time = data.get("end_time", shift["end_time"])
    role_id = data.get("role_id", shift["role_id"])
    # Only allow workers and roles that belong to this company
    if worker_id and not conn.execute("SELECT 1 FROM workers WHERE id=? AND company_id=?", (worker_id, company["id"])).fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Worker not found"}), 404
    if role_id and not conn.execute("SELECT 1 FROM roles WHERE id=? AND company_id=?", (role_id, company["id"])).fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Role not found"}), 404
    conn.execute(
        "UPDATE schedule SET worker_id=?, start_time=?, end_time=?, role_id=? WHERE id=?",
        (worker_id, start_time, end_time, role_id, shift_id),
    )
    conn.commit()
    conn.close()
    log_action(company["id"], "EDIT_SHIFT", f"Edited shift ID: {shift_id}")
    return jsonify({"status": "success"})


@app.route("/schedule/<int:shift_id>/swap", methods=["POST"])
def swap_shift(shift_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    new_worker_id = data.get("worker_id")
    conn = get_db()
    shift = conn.execute("SELECT * FROM schedule WHERE id=? AND company_id=?", (shift_id, company["id"])).fetchone()
    if not shift:
        conn.close()
        return jsonify({"status": "error", "message": "Shift not found"}), 404
    old_worker = conn.execute("SELECT name FROM workers WHERE id=?", (shift["worker_id"],)).fetchone()
    new_worker = conn.execute("SELECT name FROM workers WHERE id=? AND company_id=?", (new_worker_id, company["id"])).fetchone()
    if not new_worker:
        conn.close()
        return jsonify({"status": "error", "message": "Worker not found"}), 404
    conn.execute("UPDATE schedule SET worker_id=? WHERE id=?", (new_worker_id, shift_id))
    conn.commit()
    conn.close()
    old_name = old_worker["name"] if old_worker else "Unassigned"
    log_action(company["id"], "SWAP_SHIFT", f"Swapped shift: {old_name} -> {new_worker['name']} on {shift['day']}")
    return jsonify({"status": "success"})


@app.route("/schedule/available-workers/<int:shift_id>", methods=["GET"])
def available_for_shift(shift_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    shift = conn.execute("SELECT * FROM schedule WHERE id=? AND company_id=?", (shift_id, company["id"])).fetchone()
    if not shift:
        conn.close()
        return jsonify({"status": "error"}), 404
    workers = conn.execute("""
        SELECT DISTINCT w.id, w.name FROM workers w
        JOIN availability a ON w.id = a.worker_id
        JOIN worker_roles wr ON w.id = wr.worker_id
        WHERE a.day=? AND wr.role_id=? AND w.company_id=? AND w.id IS NOT ?
    """, (shift["day"], shift["role_id"], company["id"], shift["worker_id"])).fetchall()
    conn.close()
    return jsonify({"workers": [dict(w) for w in workers]})


@app.route("/schedule", methods=["DELETE"])
def clear_schedule():
    company = auth_required()
    if not company:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    conn = get_db()
    conn.execute("DELETE FROM schedule WHERE company_id=?", (company["id"],))
    conn.commit()
    conn.close()
    log_action(company["id"], "CLEAR_SCHEDULE", "Cleared all shifts")
    return jsonify({"status": "success", "message": "Schedule cleared"})


@app.route("/schedule/<int:shift_id>", methods=["DELETE"])
def delete_shift(shift_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    conn = get_db()
    shift = conn.execute("SELECT * FROM schedule WHERE id=? AND company_id=?", (shift_id, company["id"])).fetchone()
    if not shift:
        conn.close()
        return jsonify({"status": "error", "message": "Shift not found"}), 404
    conn.execute("DELETE FROM schedule WHERE id=?", (shift_id,))
    conn.commit()
    conn.close()
    log_action(company["id"], "DELETE_SHIFT", f"Deleted shift ID: {shift_id}")
    return jsonify({"status": "success", "message": "Shift deleted"})


# ──────────────────────────────────────────────
# SCHEDULE HISTORY
# ──────────────────────────────────────────────

@app.route("/schedule-history", methods=["GET"])
def get_schedule_history():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    histories = conn.execute(
        "SELECT id, label, created_at FROM schedule_history WHERE company_id=? ORDER BY created_at DESC LIMIT 20",
        (company["id"],),
    ).fetchall()
    result = []
    for h in histories:
        shifts = conn.execute("""
            SELECT s.day, s.start_time, s.end_time, w.name as worker, r.name as role
            FROM schedule_history_shifts s
            LEFT JOIN workers w ON s.worker_id = w.id
            LEFT JOIN roles r ON s.role_id = r.id
            WHERE s.history_id=?
            ORDER BY s.day, s.start_time
        """, (h["id"],)).fetchall()
        result.append({"id": h["id"], "label": h["label"], "created_at": h["created_at"], "shifts": [dict(s) for s in shifts]})
    conn.close()
    return jsonify({"history": result})


# ──────────────────────────────────────────────
# SCHEDULE TEMPLATES
# ──────────────────────────────────────────────

@app.route("/templates", methods=["GET"])
def get_templates():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    templates = conn.execute("SELECT id, name FROM schedule_templates WHERE company_id=? ORDER BY id DESC", (company["id"],)).fetchall()
    result = []
    for t in templates:
        shifts = conn.execute("""
            SELECT ts.day, ts.start_time, ts.end_time, ts.workers_needed, r.id as role_id, r.name as role
            FROM template_shifts ts
            LEFT JOIN roles r ON ts.role_id = r.id
            WHERE ts.template_id=?
        """, (t["id"],)).fetchall()
        result.append({"id": t["id"], "name": t["name"], "shifts": [dict(s) for s in shifts]})
    conn.close()
    return jsonify({"templates": result})


@app.route("/templates", methods=["POST"])
def save_template():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    name = data.get("name", "").strip()
    shifts = data.get("shifts", [])
    if not name or not shifts:
        return jsonify({"status": "error", "message": "Name and shifts required"}), 400
    conn = get_db()
    template_id = conn.execute(
        "INSERT INTO schedule_templates (company_id, name) VALUES (?,?)", (company["id"], name)
    ).lastrowid
    for s in shifts:
        conn.execute(
            "INSERT INTO template_shifts (template_id, day, start_time, end_time, role_id, workers_needed) VALUES (?,?,?,?,?,?)",
            (template_id, s["day"], s["start_time"], s["end_time"], s.get("role_id"), s.get("workers_needed", 1)),
        )
    conn.commit()
    conn.close()
    log_action(company["id"], "SAVE_TEMPLATE", f"Saved template: {name}")
    return jsonify({"status": "success", "id": template_id})


@app.route("/templates/<int:template_id>", methods=["DELETE"])
def delete_template(template_id):
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    # Check ownership before touching anything
    template = conn.execute("SELECT id FROM schedule_templates WHERE id=? AND company_id=?", (template_id, company["id"])).fetchone()
    if not template:
        conn.close()
        return jsonify({"status": "error", "message": "Template not found"}), 404
    conn.execute("DELETE FROM template_shifts WHERE template_id=?", (template_id,))
    conn.execute("DELETE FROM schedule_templates WHERE id=?", (template_id,))
    conn.commit()
    conn.close()
    log_action(company["id"], "DELETE_TEMPLATE", f"Deleted template ID: {template_id}")
    return jsonify({"status": "success"})


# ──────────────────────────────────────────────
# AUDIT LOG
# ──────────────────────────────────────────────

@app.route("/audit-log", methods=["GET"])
def get_audit_log():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    rows = conn.execute(
        "SELECT id, action, detail, timestamp FROM audit_log WHERE company_id=? ORDER BY timestamp DESC LIMIT 200",
        (company["id"],),
    ).fetchall()
    conn.close()
    return jsonify({"logs": [dict(r) for r in rows]})


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
    )
