import sqlite3
import os
from flask import Flask, render_template, request, jsonify

DB_PATH = os.environ.get("DB_PATH", "dod_topics.db")
app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, params=()):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


@app.route("/")
def index():
    filters = {
        "components": [
            r["component"]
            for r in query(
                "SELECT DISTINCT component FROM topics WHERE component IS NOT NULL ORDER BY component"
            )
        ],
        "statuses": [
            r["status"]
            for r in query(
                "SELECT DISTINCT status    FROM topics WHERE status    IS NOT NULL ORDER BY status"
            )
        ],
        "programs": [
            r["program"]
            for r in query(
                "SELECT DISTINCT program   FROM topics WHERE program   IS NOT NULL ORDER BY program"
            )
        ],
    }
    return render_template("index.html", filters=filters)


@app.route("/api/topics")
def api_topics():
    q = request.args.get("q", "").strip()
    comp = request.args.get("component", "")
    status = request.args.get("status", "")
    prog = request.args.get("program", "")

    where, params = ["1=1"], []
    if q:
        where.append(
            "(topic_code LIKE ? OR title LIKE ? OR keywords LIKE ? OR description LIKE ?)"
        )
        params += [f"%{q}%"] * 4
    if comp:
        where.append("component = ?")
        params.append(comp)
    if status:
        where.append("status = ?")
        params.append(status)
    if prog:
        where.append("program = ?")
        params.append(prog)

    sql = f"""
        SELECT topic_id, topic_code, title, status, component, program,
               solicitation, open_date, close_date, keywords
        FROM topics WHERE {" AND ".join(where)}
        ORDER BY topic_code
        LIMIT 500
    """
    return jsonify(query(sql, params))


@app.route("/api/topic/<topic_id>")
def api_topic(topic_id):
    rows = query("SELECT * FROM topics WHERE topic_id = ?", (topic_id,))
    if not rows:
        return jsonify({}), 404
    return jsonify(rows[0])


if __name__ == "__main__":
    app.run(debug=True, port=5050)
