import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
DATABASE = os.environ.get("DATABASE_PATH", "database.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'active' CHECK(status IN ('active','completed','archived')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_status ON items(status)
        """)


init_db()


# ── API Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    filter_status = request.args.get("status", "all")
    search = request.args.get("q", "").strip()
    db = get_db()
    query = "SELECT * FROM items"
    params = []
    conditions = []

    if filter_status != "all":
        conditions.append("status = ?")
        params.append(filter_status)
    if search:
        conditions.append("(title LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"

    items = db.execute(query, params).fetchall()
    db.close()
    return render_template("index.html", items=items, filter_status=filter_status, search=search)


@app.route("/create", methods=["POST"])
def create():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("index"))
    db = get_db()
    db.execute("INSERT INTO items (title, description) VALUES (?, ?)", (title, description))
    db.commit()
    db.close()
    flash("Item created successfully.", "success")
    return redirect(url_for("index"))


@app.route("/update/<int:item_id>", methods=["POST"])
def update(item_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "active")
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("index"))
    db = get_db()
    db.execute(
        "UPDATE items SET title=?, description=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (title, description, status, item_id),
    )
    db.commit()
    db.close()
    flash("Item updated.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:item_id>", methods=["POST"])
def delete(item_id):
    db = get_db()
    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit()
    db.close()
    flash("Item deleted.", "success")
    return redirect(url_for("index"))


@app.route("/toggle/<int:item_id>", methods=["POST"])
def toggle(item_id):
    db = get_db()
    item = db.execute("SELECT status FROM items WHERE id=?", (item_id,)).fetchone()
    if item:
        new_status = "completed" if item["status"] == "active" else "active"
        db.execute(
            "UPDATE items SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_status, item_id),
        )
        db.commit()
    db.close()
    return redirect(url_for("index"))


# ── JSON API (bonus for learners) ──────────────────────────────────────────

@app.route("/api/items", methods=["GET"])
def api_list():
    db = get_db()
    items = db.execute("SELECT * FROM items ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify([dict(i) for i in items])


@app.route("/api/items", methods=["POST"])
def api_create():
    data = request.get_json(force=True)
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO items (title, description) VALUES (?, ?)",
        (title, data.get("description", "")),
    )
    db.commit()
    item = db.execute("SELECT * FROM items WHERE id=?", (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(dict(item)), 201


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_delete(item_id):
    db = get_db()
    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit()
    db.close()
    return jsonify({"deleted": item_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG", "false").lower() == "true")
