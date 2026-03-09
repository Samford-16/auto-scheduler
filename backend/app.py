from flask import Flask, request, redirect
import sqlite3
import os

app = Flask(__name__)

def get_db():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(BASE_DIR, "workers.db")
    return sqlite3.connect(db_path)


@app.route('/add-worker', methods=['POST'])
def add_worker():

    name = request.form['worker_name']
    max_hours = request.form['max_hours']
    overtime = request.form['overtime']

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO workers (name, max_hours, overtime_allowed) VALUES (?, ?, ?)",
        (name, max_hours, overtime)
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard.html")


@app.route("/workers")
def workers():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM workers")
    data = cursor.fetchall()

    conn.close()

    return {"workers": data}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)