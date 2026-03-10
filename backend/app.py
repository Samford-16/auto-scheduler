from flask import Flask, request, jsonify
from flask_cors import CORS
from database import get_db, init_db

app = Flask(__name__)
CORS(app)
init_db()

# ──────────────────────────────────────────────
# COMPANY
# ──────────────────────────────────────────────

@app.route("/company", methods=["GET"])
def get_company():
    conn = get_db()
    company = conn.execute("SELECT * FROM company LIMIT 1").fetchone()
    conn.close()
    if company:
        return jsonify({"company": dict(company)})
    return jsonify({"company": None})

@app.route("/company", methods=["POST"])
def save_company():
    data = request.json
    conn = get_db()
    existing = conn.execute("SELECT * FROM company LIMIT 1").fetchone()
    if existing:
        conn.execute("UPDATE company SET name=?, open_time=?, close_time=? WHERE id=?",
                     (data["name"], data["open_time"], data["close_time"], existing["id"]))
    else:
        conn.execute("INSERT INTO company (name, open_time, close_time) VALUES (?,?,?)",
                     (data["name"], data["open_time"], data["close_time"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

# ──────────────────────────────────────────────
# ROLES
# ──────────────────────────────────────────────

@app.route("/roles", methods=["GET"])
def get_roles():
    conn = get_db()
    roles = conn.execute("SELECT * FROM roles").fetchall()
    conn.close()
    return jsonify({"roles": [dict(r) for r in roles]})

@app.route("/roles", methods=["POST"])
def add_role():
    data = request.json
    conn = get_db()
    try:
        conn.execute("INSERT INTO roles (name) VALUES (?)", (data["name"],))
        conn.commit()
    except:
        conn.close()
        return jsonify({"status": "error", "message": "Role already exists"}), 400
    conn.close()
    return jsonify({"status": "success"})

@app.route("/roles/<int:role_id>", methods=["DELETE"])
def delete_role(role_id):
    conn = get_db()
    conn.execute("DELETE FROM roles WHERE id=?", (role_id,))
    conn.execute("DELETE FROM worker_roles WHERE role_id=?", (role_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# ──────────────────────────────────────────────
# WORKERS
# ──────────────────────────────────────────────

@app.route("/workers", methods=["GET"])
def get_workers():
    conn = get_db()
    workers = conn.execute("SELECT * FROM workers").fetchall()
    result = []
    for w in workers:
        availability = conn.execute(
            "SELECT day FROM availability WHERE worker_id=?", (w["id"],)
        ).fetchall()
        roles = conn.execute(
            """SELECT r.id, r.name FROM roles r
               JOIN worker_roles wr ON r.id = wr.role_id
               WHERE wr.worker_id=?""", (w["id"],)
        ).fetchall()
        days = [d["day"] for d in availability]
        result.append({
            "id": w["id"],
            "name": w["name"],
            "max_hours": w["max_hours"],
            "overtime": w["overtime"],
            "availability": days,
            "roles": [dict(r) for r in roles]
        })
    conn.close()
    return jsonify({"workers": result})

@app.route("/add-worker", methods=["POST"])
def add_worker():
    data = request.json
    name = data["name"]
    max_hours = data["max_hours"]
    overtime = data["overtime"]
    days = data["availability"]
    role_ids = data.get("roles", [])

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO workers (name, max_hours, overtime) VALUES (?,?,?)",
        (name, max_hours, overtime)
    )
    worker_id = cursor.lastrowid

    for day in days:
        conn.execute("INSERT INTO availability (worker_id, day) VALUES (?,?)", (worker_id, day))

    for role_id in role_ids:
        conn.execute("INSERT INTO worker_roles (worker_id, role_id) VALUES (?,?)", (worker_id, role_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route("/delete-worker/<int:worker_id>", methods=["DELETE"])
def delete_worker(worker_id):
    conn = get_db()
    conn.execute("DELETE FROM availability WHERE worker_id=?", (worker_id,))
    conn.execute("DELETE FROM worker_roles WHERE worker_id=?", (worker_id,))
    conn.execute("DELETE FROM workers WHERE id=?", (worker_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# ──────────────────────────────────────────────
# SCHEDULE
# ──────────────────────────────────────────────

@app.route("/generate-schedule", methods=["POST"])
def generate_schedule():
    data = request.json
    # data = { shifts: [ {day, start_time, end_time, role_id, workers_needed}, ... ] }
    shifts = data.get("shifts", [])

    conn = get_db()
    conn.execute("DELETE FROM schedule")  # clear old schedule

    workers = conn.execute("SELECT * FROM workers").fetchall()

    # Track hours assigned per worker this week
    hours_used = {w["id"]: 0 for w in workers}

    assigned = []

    for shift in shifts:
        day = shift["day"]
        start = shift["start_time"]
        end = shift["end_time"]
        role_id = shift["role_id"]
        needed = int(shift["workers_needed"])

        # Calculate shift hours
        from datetime import datetime
        fmt = "%H:%M"
        try:
            shift_hours = (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).seconds / 3600
        except:
            shift_hours = 8

        # Get available workers for this day with the right role
        eligible = conn.execute("""
            SELECT w.* FROM workers w
            JOIN availability a ON w.id = a.worker_id
            JOIN worker_roles wr ON w.id = wr.worker_id
            WHERE a.day=? AND wr.role_id=?
        """, (day, role_id)).fetchall()

        count = 0
        for worker in eligible:
            if count >= needed:
                break
            wid = worker["id"]
            max_h = worker["max_hours"]
            allows_ot = worker["overtime"] == "yes"

            projected = hours_used[wid] + shift_hours
            if projected > max_h and not allows_ot:
                continue  # skip, would exceed max hours

            conn.execute(
                "INSERT INTO schedule (worker_id, day, start_time, end_time, role_id) VALUES (?,?,?,?,?)",
                (wid, day, start, end, role_id)
            )
            hours_used[wid] = projected
            assigned.append({
                "worker": worker["name"],
                "day": day,
                "start_time": start,
                "end_time": end,
                "role_id": role_id
            })
            count += 1

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "assigned": assigned})

@app.route("/schedule", methods=["GET"])
def get_schedule():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.day, s.start_time, s.end_time, w.name as worker, r.name as role
        FROM schedule s
        JOIN workers w ON s.worker_id = w.id
        LEFT JOIN roles r ON s.role_id = r.id
        ORDER BY s.day, s.start_time
    """).fetchall()
    conn.close()
    return jsonify({"schedule": [dict(r) for r in rows]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)