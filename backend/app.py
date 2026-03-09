from flask import Flask, request, jsonify
from flask_cors import CORS
from database import get_db, init_db

app = Flask(__name__)
CORS(app)

# initialize database on startup
init_db()


@app.route("/workers", methods=["GET"])
def workers():
    conn = get_db()
    workers = conn.execute("SELECT * FROM workers").fetchall()
    conn.close()

    return jsonify({
        "workers": [list(worker) for worker in workers]
    })


@app.route("/add-worker", methods=["POST"])
def add_worker():

    data = request.json

    name = data["name"]
    max_hours = data["max_hours"]
    overtime = data["overtime"]

    conn = get_db()

    conn.execute(
        "INSERT INTO workers (name, max_hours, overtime) VALUES (?, ?, ?)",
        (name, max_hours, overtime)
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


@app.route("/delete-worker/<int:worker_id>", methods=["DELETE"])
def delete_worker(worker_id):

    conn = get_db()

    conn.execute(
        "DELETE FROM workers WHERE id = ?",
        (worker_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)