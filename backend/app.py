from flask import Flask, request, redirect
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)

CORS(app)

def get_db():

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(BASE_DIR,"../database/workers.db")

return sqlite3.connect(db_path)


@app.route("/add-worker",methods=["POST"])
def add_worker():

name = request.form["name"]
max_hours = request.form["max_hours"]
overtime = request.form["overtime"]

conn = get_db()
cursor = conn.cursor()

cursor.execute("""

INSERT INTO workers(name,max_hours,overtime)

VALUES(?,?,?)

""",(name,max_hours,overtime))

conn.commit()
conn.close()

return redirect("http://34.28.196.192/dashboard.html")


@app.route("/workers")
def workers():

conn = get_db()

cursor = conn.cursor()

cursor.execute("SELECT * FROM workers")

data = cursor.fetchall()

conn.close()

return {"workers":data}


@app.route("/delete-worker/<int:id>",methods=["DELETE"])
def delete_worker(id):

conn = get_db()
cursor = conn.cursor()

cursor.execute("DELETE FROM workers WHERE id=?",(id,))

conn.commit()
conn.close()

return {"status":"deleted"}


if __name__ == "__main__":

app.run(host="0.0.0.0",port=5000)