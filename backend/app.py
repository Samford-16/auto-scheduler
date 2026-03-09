from flask import Flask, request, jsonify
from flask_cors import CORS
from database import get_db, init_db

app = Flask(__name__)
CORS(app)

init_db()


@app.route("/workers", methods=["GET"])
def workers():

    conn = get_db()

    workers = conn.execute("SELECT * FROM workers").fetchall()

    result = []

    for worker in workers:

        availability = conn.execute(
            "SELECT day FROM availability WHERE worker_id=?",
            (worker["id"],)
        ).fetchall()

        days = [d["day"] for d in availability]

        result.append({
            "id": worker["id"],
            "name": worker["name"],
            "max_hours": worker["max_hours"],
            "overtime": worker["overtime"],
            "availability": days
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

    conn = get_db()

    cursor = conn.execute(
        "INSERT INTO workers (name,max_hours,overtime) VALUES (?,?,?)",
        (name,max_hours,overtime)
    )

    worker_id = cursor.lastrowid

    for day in days:

        conn.execute(
            "INSERT INTO availability (worker_id,day) VALUES (?,?)",
            (worker_id,day)
        )

    conn.commit()
    conn.close()

    return jsonify({"status":"success"})


@app.route("/delete-worker/<int:worker_id>", methods=["DELETE"])
def delete_worker(worker_id):

    conn = get_db()

    conn.execute("DELETE FROM availability WHERE worker_id=?", (worker_id,))
    conn.execute("DELETE FROM workers WHERE id=?", (worker_id,))

    conn.commit()
    conn.close()

    return jsonify({"status":"deleted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)