from flask import Flask, request, jsonify
from flask_cors import CORS
from database import get_db, init_db
import hashlib
import secrets
from datetime import datetime

app = Flask(__name__)
CORS(app)
init_db()

# ──────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_company_from_token(token):
    if not token:
        return None
    conn = get_db()
    company = conn.execute("SELECT * FROM companies WHERE token=?", (token,)).fetchone()
    conn.close()
    return company

def auth_required():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    company = get_company_from_token(token)
    return company

# ──────────────────────────────────────────────
# AUDIT LOG HELPER
# ──────────────────────────────────────────────

def log_action(company_id, action, detail=""):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_log (company_id, action, detail, timestamp) VALUES (?, ?, ?, ?)",
            (company_id, action, detail, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
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

    conn = get_db()
    existing = conn.execute("SELECT id FROM companies WHERE email=?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "Email already registered"}), 400

    token = secrets.token_hex(32)
    hashed = hash_password(password)
    conn.execute("INSERT INTO companies (name, email, password, token) VALUES (?,?,?,?)", (name, email, hashed, token))
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
    if not company or company["password"] != hash_password(password):
        conn.close()
        return jsonify({"status": "error", "message": "Invalid email or password"}), 401
    token = secrets.token_hex(32)
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
    conn.execute("UPDATE companies SET name=?, open_time=?, close_time=? WHERE id=?", (data["name"], data["open_time"], data["close_time"], company["id"]))
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
    if role:
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
        roles = conn.execute("""SELECT r.id, r.name FROM roles r JOIN worker_roles wr ON r.id = wr.role_id WHERE wr.worker_id=?""", (w["id"],)).fetchall()
        result.append({
            "id": w["id"], "name": w["name"], "max_hours": w["max_hours"],
            "overtime": w["overtime"], "notes": w["notes"] or "",
            "availability": [d["day"] for d in availability],
            "roles": [dict(r) for r in roles]
        })
    conn.close()
    return jsonify({"workers": result})

@app.route("/add-worker", methods=["POST"])
def add_worker():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO workers (company_id, name, max_hours, overtime, notes) VALUES (?,?,?,?,?)",
        (company["id"], data["name"], data["max_hours"], data["overtime"], data.get("notes", ""))
    )
    worker_id = cursor.lastrowid
    for day in data.get("availability", []):
        conn.execute("INSERT INTO availability (worker_id, day) VALUES (?,?)", (worker_id, day))
    for role_id in data.get("roles", []):
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
    notes = data.get("notes", "")
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
    for role_id in role_ids:
        role = conn.execute("SELECT * FROM roles WHERE id=? AND company_id=?", (role_id, company["id"])).fetchone()
        if role:
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
# SCHEDULE
# ──────────────────────────────────────────────

@app.route("/generate-schedule", methods=["POST"])
def generate_schedule():
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    data = request.json
    shifts = data.get("shifts", [])
    label = data.get("label", datetime.utcnow().strftime("Week of %b %d, %Y"))
    conn = get_db()

    # Archive current schedule before wiping
    existing = conn.execute("SELECT COUNT(*) as cnt FROM schedule WHERE company_id=?", (company["id"],)).fetchone()
    if existing["cnt"] > 0:
        archive_id = conn.execute(
            "INSERT INTO schedule_history (company_id, label, created_at) VALUES (?,?,?)",
            (company["id"], label, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        ).lastrowid
        rows = conn.execute("SELECT * FROM schedule WHERE company_id=?", (company["id"],)).fetchall()
        for r in rows:
            conn.execute(
                "INSERT INTO schedule_history_shifts (history_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (archive_id, r["worker_id"], r["day"], r["start_time"], r["end_time"], r["role_id"])
            )

    # Save the shift requirements so Refresh can replay them
    import json
    conn.execute("DELETE FROM last_shift_requirements WHERE company_id=?", (company["id"],))
    conn.execute("INSERT INTO last_shift_requirements (company_id, shifts_json) VALUES (?,?)",
        (company["id"], json.dumps(shifts)))

    conn.execute("DELETE FROM schedule WHERE company_id=?", (company["id"],))
    workers = conn.execute("SELECT * FROM workers WHERE company_id=?", (company["id"],)).fetchall()
    hours_used = {w["id"]: 0 for w in workers}
    # Track which workers are already assigned on each day — one shift per worker per day
    assigned_today = {w["id"]: set() for w in workers}  # {worker_id: {day, ...}}
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
        except:
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
            # One shift per worker per day — skip if already working that day
            if day in assigned_today[wid]:
                continue
            projected = hours_used[wid] + shift_hours
            if projected > worker["max_hours"] and worker["overtime"] != "yes":
                continue
            conn.execute(
                "INSERT INTO schedule (company_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (company["id"], wid, day, start, end, role_id)
            )
            hours_used[wid] = projected
            assigned_today[wid].add(day)
            assigned.append({"worker": worker["name"], "day": day})
            count += 1
        # Insert blank placeholder rows for unfilled slots
        for _ in range(needed - count):
            conn.execute(
                "INSERT INTO schedule (company_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (company["id"], None, day, start, end, role_id)
            )
            unassigned.append({"day": day, "start": start, "end": end, "role_id": role_id, "needed": needed, "filled": count})

    conn.commit()
    conn.close()
    log_action(company["id"], "GENERATE_SCHEDULE", f"Generated {len(assigned)} shift assignments ({len(unassigned)} slots unfilled)")
    return jsonify({"status": "success", "assigned": assigned, "unassigned": unassigned})

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
    conn.execute(
        "UPDATE schedule SET worker_id=?, start_time=?, end_time=?, role_id=? WHERE id=?",
        (worker_id, start_time, end_time, role_id, shift_id)
    )
    conn.commit()
    conn.close()
    log_action(company["id"], "EDIT_SHIFT", f"Edited shift ID: {shift_id}")
    return jsonify({"status": "success"})

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
    log_action(company["id"], "SWAP_SHIFT", f"Swapped shift: {old_worker['name']} -> {new_worker['name']} on {shift['day']}")
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
        WHERE a.day=? AND wr.role_id=? AND w.company_id=? AND w.id != ?
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
        (company["id"],)
    ).fetchall()
    result = []
    for h in histories:
        shifts = conn.execute("""
            SELECT s.day, s.start_time, s.end_time, w.name as worker, r.name as role
            FROM schedule_history_shifts s
            JOIN workers w ON s.worker_id = w.id
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
            (template_id, s["day"], s["start_time"], s["end_time"], s.get("role_id"), s.get("workers_needed", 1))
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
    conn.execute("DELETE FROM template_shifts WHERE template_id=?", (template_id,))
    conn.execute("DELETE FROM schedule_templates WHERE id=? AND company_id=?", (template_id, company["id"]))
    conn.commit()
    conn.close()
    log_action(company["id"], "DELETE_TEMPLATE", f"Deleted template ID: {template_id}")
    return jsonify({"status": "success"})

# ──────────────────────────────────────────────
# REFRESH SCHEDULE
# ──────────────────────────────────────────────

@app.route("/refresh-schedule", methods=["POST"])
def refresh_schedule():
    import json
    company = auth_required()
    if not company:
        return jsonify({"status": "error"}), 401
    conn = get_db()
    row = conn.execute("SELECT shifts_json FROM last_shift_requirements WHERE company_id=?", (company["id"],)).fetchone()
    conn.close()
    if not row:
        return jsonify({"status": "error", "message": "No previous schedule found"}), 404
    # Replay using the saved shifts
    from flask import request as freq
    import json as j
    saved = j.loads(row["shifts_json"])
    # Inject into request and call generate
    with app.test_request_context(json={"shifts": saved}, headers={"Authorization": request.headers.get("Authorization","")}):
        pass
    # Call generate directly with saved data
    data_backup = request.json if request.is_json else {}
    # Use internal call approach
    return generate_schedule_with(company, saved)

def generate_schedule_with(company, shifts):
    import json
    conn = get_db()
    label = datetime.utcnow().strftime("Week of %b %d, %Y")

    existing = conn.execute("SELECT COUNT(*) as cnt FROM schedule WHERE company_id=?", (company["id"],)).fetchone()
    if existing["cnt"] > 0:
        archive_id = conn.execute(
            "INSERT INTO schedule_history (company_id, label, created_at) VALUES (?,?,?)",
            (company["id"], label, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        ).lastrowid
        rows = conn.execute("SELECT * FROM schedule WHERE company_id=?", (company["id"],)).fetchall()
        for r in rows:
            conn.execute(
                "INSERT INTO schedule_history_shifts (history_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (archive_id, r["worker_id"], r["day"], r["start_time"], r["end_time"], r["role_id"])
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
        except:
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
                (company["id"], wid, day, start, end, role_id)
            )
            hours_used[wid] = projected
            assigned_today[wid].add(day)
            assigned.append({"worker": worker["name"], "day": day})
            count += 1
        for _ in range(needed - count):
            conn.execute(
                "INSERT INTO schedule (company_id, worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?,?)",
                (company["id"], None, day, start, end, role_id)
            )
            unassigned.append({"day": day, "start": start, "end": end, "role_id": role_id, "needed": needed, "filled": count})

    conn.commit()
    conn.close()
    log_action(company["id"], "GENERATE_SCHEDULE", f"Refreshed: {len(assigned)} assigned, {len(unassigned)} unfilled")
    return jsonify({"status": "success", "assigned": assigned, "unassigned": unassigned})

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
        (company["id"],)
    ).fetchall()
    conn.close()
    return jsonify({"logs": [dict(r) for r in rows]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)