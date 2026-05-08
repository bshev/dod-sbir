import sqlite3
import os
from flask import Flask, render_template, request, jsonify

_HERE       = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.environ.get("DB_PATH",     os.path.join(_HERE, "..", "dod_sbir.db"))
SCORES_PATH = os.environ.get("SCORES_PATH", os.path.join(_HERE, "..", "scores.db"))
app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_scores():
    with sqlite3.connect(SCORES_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                topic_id TEXT PRIMARY KEY,
                score    INTEGER
            )
        """)


def query(sql, params=()):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_with_scores(sql, params=()):
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(f"ATTACH DATABASE '{SCORES_PATH}' AS sdb")
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


@app.route("/")
def index():
    filters = {
        "programs": [r["program"] for r in query("SELECT DISTINCT program FROM topics WHERE program IS NOT NULL ORDER BY program")],
    }
    return render_template("index.html", filters=filters)


@app.route("/api/topics")
def api_topics():
    q         = request.args.get("q", "").strip()
    prog      = request.args.get("program", "")
    min_score = request.args.get("min_score", "")

    where, params = ["1=1"], []
    if q:
        where.append("(t.topic_code LIKE ? OR t.title LIKE ? OR t.keywords LIKE ? OR t.description LIKE ?)")
        params += [f"%{q}%"] * 4
    if prog:
        where.append("t.program = ?"); params.append(prog)
    if min_score != "":
        where.append("(s.score IS NULL OR s.score >= ?)"); params.append(int(min_score))

    sql = f"""
        SELECT t.topic_id, t.topic_code, t.title, t.component, t.program,
               t.open_date, t.close_date, t.keywords,
               s.score
        FROM topics t
        LEFT JOIN sdb.scores s ON s.topic_id = t.topic_id
        WHERE {" AND ".join(where)}
        ORDER BY t.topic_code
        LIMIT 500
    """
    return jsonify(query_with_scores(sql, params))


@app.route("/api/topic/<topic_id>")
def api_topic(topic_id):
    sql = """
        SELECT t.*, s.score
        FROM topics t
        LEFT JOIN sdb.scores s ON s.topic_id = t.topic_id
        WHERE t.topic_id = ?
    """
    rows = query_with_scores(sql, (topic_id,))
    if not rows:
        return jsonify({}), 404
    return jsonify(rows[0])


@app.route("/api/topic/<topic_id>/score", methods=["POST"])
def set_score(topic_id):
    data = request.get_json()
    score = data.get("score")
    if score is not None and score not in range(1, 6):
        return jsonify({"error": "score must be 1-5"}), 400
    with sqlite3.connect(SCORES_PATH) as conn:
        if score is None:
            conn.execute("DELETE FROM scores WHERE topic_id = ?", (topic_id,))
        else:
            conn.execute(
                "INSERT INTO scores (topic_id, score) VALUES (?, ?) "
                "ON CONFLICT(topic_id) DO UPDATE SET score = excluded.score",
                (topic_id, score),
            )
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_scores()
    app.run(debug=True, port=5050)
