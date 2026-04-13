"""
flask_api.py — IT Jobs PH authentication API (Flask)
Backed by SQLite + Fernet encryption via database.py.

Routes (unchanged — auth.py in Streamlit needs zero edits):
  POST  /auth/login
  POST  /auth/register
  GET   /auth/verify      (JWT required)
  GET   /auth/users       (admin only)
  POST  /auth/promote     (admin only)
  GET   /health

Run with:
    python flask_api.py
"""

import os
import bcrypt
from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity, get_jwt,
)
from flask_cors import CORS
from datetime import timedelta
from dotenv import load_dotenv

from database import init_db, get_user, create_user, set_role, list_users

load_dotenv()

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

jwt_secret = os.environ.get("JWT_SECRET_KEY")
if not jwt_secret:
    raise RuntimeError("JWT_SECRET_KEY not set — add it to your .env file.")

app.config["JWT_SECRET_KEY"] = jwt_secret
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)

jwt = JWTManager(app)

# Initialise DB (creates table + seeds default admin if needed)
init_db()


# ── Password helpers ──────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    user = get_user(username)

    # Same error for missing user vs wrong password (prevents user enumeration)
    if user is None or not _check_password(password, user["password"]):
        return jsonify({"error": "Incorrect username or password."}), 401

    token = create_access_token(
        identity=username,
        additional_claims={"role": user["role"]},
    )
    return jsonify({"token": token, "role": user["role"], "username": username}), 200


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    
    # Password validation
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long."}), 400
    import re
    if not re.search(r"\d", password):
        return jsonify({"error": "Password must contain at least one number."}), 400
    if not re.search(r"[a-zA-Z]", password):
        return jsonify({"error": "Password must contain at least one letter."}), 400

    ok, err = create_user(username, _hash_password(password), role="user")
    if not ok:
        return jsonify({"error": err}), 409

    token = create_access_token(
        identity=username,
        additional_claims={"role": "user"},
    )
    return jsonify({
        "token":    token,
        "role":     "user",
        "username": username,
        "message":  "Account created successfully.",
    }), 201


@app.route("/auth/verify", methods=["GET"])
@jwt_required()
def verify():
    username = get_jwt_identity()
    user = get_user(username)

    if user is None:
        return jsonify({"error": "User no longer exists."}), 401

    # Always return freshest role from DB (not just what's in the token)
    return jsonify({"username": username, "role": user["role"], "valid": True}), 200


@app.route("/auth/users", methods=["GET"])
@jwt_required()
def list_all_users():
    """Admin only — list all users and their roles."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    return jsonify({"users": list_users()}), 200


@app.route("/auth/promote", methods=["POST"])
@jwt_required()
def promote():
    """Admin only — promote or demote a user.
    Body: { "username": "sean", "role": "admin" }
    """
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    data = request.get_json()
    target = (data.get("username") or "").strip().lower()
    new_role = data.get("role", "user")

    if new_role not in ("admin", "user"):
        return jsonify({"error": "Role must be 'admin' or 'user'."}), 400

    if not get_user(target):
        return jsonify({"error": f"User '{target}' not found."}), 404

    set_role(target, new_role)
    return jsonify({
        "message":  f"{target} is now {new_role}.",
        "username": target,
        "role":     new_role,
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "IT Jobs PH API"}), 200


if __name__ == "__main__":
    print("Starting IT Jobs PH Flask API on http://localhost:5050")
    app.run(port=5050, debug=True)