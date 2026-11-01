
import os

from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from difflib import SequenceMatcher

from db import get_connection


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

if not app.secret_key or not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
    raise RuntimeError("Missing security settings in .env file.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)


@app.route("/")
def home():
    success = request.args.get("success")
    duplicate = request.args.get("duplicate")

    connection = None
    cursor = None
    complaints = []

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM complaints ORDER BY created_at DESC"
        )
        complaints = cursor.fetchall()

    except Exception:
        app.logger.exception("Could not load complaints")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    return render_template(
        "index.html",
        success=success,
        duplicate=duplicate,
        complaints=complaints
    )


@app.route("/report", methods=["POST"])
def report():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    location = request.form.get("location", "").strip()

    latitude = request.form.get("latitude", "").strip()
    longitude = request.form.get("longitude", "").strip()

    if not all([title, description, category, location]):
        return "Please fill in all fields.", 400

    try:
        latitude = float(latitude)
        longitude = float(longitude)

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return "Invalid map coordinates.", 400

    except (ValueError, TypeError):
        return "Please select a valid location on the map.", 400

    text = (title + " " + description + " " + category).lower()

    high_words = [
        "dangerous", "accident", "urgent", "overflow",
        "severe", "blocked road", "major"
    ]

    medium_words = [
        "pothole", "drainage", "garbage",
        "streetlight", "broken", "blocked"
    ]

    if any(word in text for word in high_words):
        priority = "High"
    elif any(word in text for word in medium_words):
        priority = "Medium"
    else:
        priority = "Low"

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT title, location FROM complaints")
        existing_complaints = cursor.fetchall()

        duplicate_found = False

        for old_title, old_location in existing_complaints:
            title_similarity = SequenceMatcher(
                None, title.lower(), old_title.lower()
            ).ratio()

            same_location = (
                location.lower() == old_location.lower()
                if old_location else False
            )

            if title_similarity >= 0.75 and same_location:
                duplicate_found = True
                break

        query = """
        INSERT INTO complaints
        (title, description, category, location, priority, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                title,
                description,
                category,
                location,
                priority,
                latitude,
                longitude
            )
        )

        connection.commit()

        return redirect(url_for(
            "home",
            success="1",
            duplicate="1" if duplicate_found else "0"
        ))

    except Exception:
        app.logger.exception("Failed to save complaint")
        return "Could not save complaint. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if (
            username == ADMIN_USERNAME
            and check_password_hash(ADMIN_PASSWORD_HASH, password)
        ):
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))

        error = "Invalid username or password"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    connection = None
    cursor = None
    complaints = []

    total = 0
    pending = 0
    in_progress = 0
    resolved = 0
    high = 0
    medium = 0
    low = 0

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM complaints ORDER BY created_at DESC"
        )
        complaints = cursor.fetchall()

        total = len(complaints)

        pending = sum(1 for c in complaints if c["status"] == "Pending")
        in_progress = sum(1 for c in complaints if c["status"] == "In Progress")
        resolved = sum(1 for c in complaints if c["status"] == "Resolved")

        high = sum(1 for c in complaints if c["priority"] == "High")
        medium = sum(1 for c in complaints if c["priority"] == "Medium")
        low = sum(1 for c in complaints if c["priority"] == "Low")

    except Exception:
        app.logger.exception("Could not load admin dashboard")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    return render_template(
        "admin.html",
        complaints=complaints,
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        high=high,
        medium=medium,
        low=low
    )


@app.route("/update_status", methods=["POST"])
def update_status():
    if not session.get("admin"):
        return redirect(url_for("login"))

    complaint_id = request.form.get("complaint_id")
    status = request.form.get("status")

    allowed_statuses = ["Pending", "In Progress", "Resolved"]

    if status not in allowed_statuses:
        return "Invalid status", 400

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE complaints SET status = %s WHERE id = %s",
            (status, complaint_id)
        )

        connection.commit()

    except Exception:
        app.logger.exception("Could not update complaint status")
        return "Could not update status. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True)
