import os
import psycopg2
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")

DB = os.environ["DATABASE_URL"]

def conn():
    return psycopg2.connect(DB)

def init():
    with conn() as c:
        c.cursor().execute("""
            CREATE TABLE IF NOT EXISTS coinflip_votes (
                student_id   TEXT PRIMARY KEY,
                student_name TEXT,
                choice       TEXT CHECK(choice IN ('A','B')),
                voted_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        c.commit()

init()

@app.route("/api/vote", methods=["POST"])
def vote():
    d = request.json or {}
    sid, name, choice = d.get("id",""), d.get("name",""), d.get("choice","")
    if not sid or choice not in ("A","B"):
        return jsonify(error="invalid"), 400
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT choice FROM coinflip_votes WHERE student_id=%s", (sid,))
        row = cur.fetchone()
        if row:
            return jsonify(error="already_voted", choice=row[0]), 409
        cur.execute(
            "INSERT INTO coinflip_votes (student_id, student_name, choice) VALUES (%s,%s,%s)",
            (sid, name, choice)
        )
        c.commit()
    return jsonify(ok=True, choice=choice)

@app.route("/api/check/<sid>")
def check(sid):
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT choice FROM coinflip_votes WHERE student_id=%s", (sid,))
        row = cur.fetchone()
    return jsonify(voted=bool(row), choice=row[0] if row else None)

@app.route("/api/tally")
def tally():
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT choice, COUNT(*) FROM coinflip_votes GROUP BY choice")
        rows = cur.fetchall()
    t = {r[0]: r[1] for r in rows}
    return jsonify(A=t.get("A",0), B=t.get("B",0))

ADMIN = """<!DOCTYPE html>
<html><head><meta charset=UTF-8><title>Resultados – ESPAM MFL</title>
<style>
body{font-family:system-ui;padding:2rem;max-width:620px;margin:0 auto;color:#1a1a1a}
h1{font-size:20px;font-weight:600;margin-bottom:1.5rem}
.opt{font-size:14px;margin-bottom:4px}
.bar{height:10px;background:#eee;border-radius:5px;overflow:hidden;margin-bottom:14px}
.fill{height:100%;border-radius:5px}
.meta{font-size:12px;color:#aaa;margin-bottom:1.5rem}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 10px;border-bottom:2px solid #eee;color:#888;font-weight:500}
td{padding:8px 10px;border-bottom:1px solid #f5f5f5}
.A{color:#378ADD;font-weight:600}.B{color:#D85A30;font-weight:600}
</style></head><body>
<h1>Resultados del voto · ESPAM MFL</h1>
{% set total = votes|length %}
{% set a = votes|selectattr('choice','eq','A')|list|length %}
{% set b = total - a %}
{% set pa = ((a/total*100)|round|int) if total > 0 else 50 %}
{% set pb = 100 - pa %}
<div class=opt>🌅 10:00 – 11:00 A.M. &nbsp;<strong>{{ a }} votos ({{ pa }}%)</strong></div>
<div class=bar><div class=fill style="width:{{pa}}%;background:#378ADD"></div></div>
<div class=opt>🌇 4:00 – 5:00 P.M. &nbsp;<strong>{{ b }} votos ({{ pb }}%)</strong></div>
<div class=bar><div class=fill style="width:{{pb}}%;background:#D85A30"></div></div>
<p class=meta>{{ total }} de 35 estudiantes han votado</p>
<table>
<tr><th>#</th><th>Estudiante</th><th>Voto</th><th>Hora</th></tr>
{% for v in votes %}
<tr>
  <td>{{ loop.index }}</td>
  <td>{{ v.name }}</td>
  <td class="{{ v.choice }}">{{ '10:00 A.M.' if v.choice == 'A' else '4:00 P.M.' }}</td>
  <td>{{ v.voted_at.strftime('%H:%M:%S') }}</td>
</tr>
{% endfor %}
</table>
</body></html>"""

@app.route("/admin")
def admin():
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT student_name, choice, voted_at FROM coinflip_votes ORDER BY voted_at")
        rows = cur.fetchall()
    votes = [{"name": r[0], "choice": r[1], "voted_at": r[2]} for r in rows]
    return render_template_string(ADMIN, votes=votes)

@app.route("/api/reset", methods=["POST"])
def reset():
    key = request.json.get("key","")
    if key != os.environ.get("ADMIN_KEY","changeme"):
        return jsonify(error="unauthorized"), 401
    with conn() as c:
        c.cursor().execute("DELETE FROM coinflip_votes")
        c.commit()
    return jsonify(ok=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
