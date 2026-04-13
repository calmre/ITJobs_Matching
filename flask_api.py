import os
import json
import bcrypt
from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity, get_jwt
)
from flask_cors import CORS
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── JWT config ────────────────────────────────────────────────────────────────
jwt_secret = os.environ.get("JWT_SECRET_KEY")
if not jwt_secret:
    raise RuntimeError("JWT_SECRET_KEY not set — add it to your .env file.")
app.config["JWT_SECRET_KEY"] = jwt_secret
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)

jwt = JWTManager(app)

# ── User store ────────────────────────────────────────────────────────────────
# CHANGED: users.json now stores both password hash AND role per user.
#
# New format:
# {
#   "admin": { "password": "<bcrypt hash>", "role": "admin" },
#   "sean":  { "password": "<bcrypt hash>", "role": "user"  }
# }
#
# Old format was just { "username": "<hash>" } — we handle migration below
# so your existing users.json keeps working without any manual changes.

USER_DB_FILE = "users.json"

DEFAULT_USERS = {
    "admin": {
        "password": "$2b$12$kpfPX8DsKINFIGB5nEkrkOla0Kkr9mdzm1Pk1WN4bWThps9EA640O",
        "role": "admin"
    }
}


def _migrate_users(users: dict) -> dict:
    """
    Migrate old format { username: hash_string } to new format
    { username: { password: hash, role: role } }.

    This runs transparently on every load — old entries get upgraded,
    new entries are left alone. Safe to run multiple times.
    """
    migrated = {}
    changed = False
    for username, value in users.items():
        if isinstance(value, str):
            # Old format — value is just the hash string
            migrated[username] = {
                "password": value,
                "role": "admin" if username == "admin" else "user"
            }
            changed = True
        else:
            # Already new format
            migrated[username] = value
    return migrated, changed


def _load_users() -> dict:
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "w") as f:
            json.dump(DEFAULT_USERS, f, indent=2)
        return DEFAULT_USERS.copy()

    with open(USER_DB_FILE, "r") as f:
        users = json.load(f)

    # Migrate old format if needed — saves back automatically
    users, changed = _migrate_users(users)
    if changed:
        _save_users(users)

    return users


def _save_users(users: dict):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _get_role(username: str, users: dict) -> str:
    """Get the role for a user from the users dict."""
    return users.get(username, {}).get("role", "user")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    users = _load_users()

    if username not in users:
        return jsonify({"error": "Incorrect username or password."}), 401

    stored_hash = users[username]["password"]
    if not _check_password(password, stored_hash):
        return jsonify({"error": "Incorrect username or password."}), 401

    # Role comes from users.json — not hardcoded anymore
    role = _get_role(username, users)

    token = create_access_token(
        identity=username,
        additional_claims={"role": role}
    )

    return jsonify({"token": token, "role": role, "username": username}), 200


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters."}), 400

    users = _load_users()

    if username in users:
        return jsonify({"error": "Username already exists."}), 409

    # New registrations are always "user" — admin promotes them via /auth/promote
    users[username] = {
        "password": _hash_password(password),
        "role": "user"
    }
    _save_users(users)

    token = create_access_token(
        identity=username,
        additional_claims={"role": "user"}
    )

    return jsonify({
        "token": token,
        "role": "user",
        "username": username,
        "message": "Account created successfully.",
    }), 201


@app.route("/auth/verify", methods=["GET"])
@jwt_required()
def verify():
    username = get_jwt_identity()
    
    # Query database to get the freshest role, in case it was updated manually
    # or by an admin since the token was issued.
    users = _load_users()
    if username not in users:
        return jsonify({"error": "User no longer exists"}), 401
    
    role = _get_role(username, users)
    
    return jsonify({"username": username, "role": role, "valid": True}), 200


@app.route("/auth/users", methods=["GET"])
@jwt_required()
def list_users():
    """Admin only — list all users and their roles."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    users = _load_users()
    return jsonify({
        "users": [
            {"username": u, "role": v["role"]}
            for u, v in users.items()
        ]
    }), 200


@app.route("/auth/promote", methods=["POST"])
@jwt_required()
def promote():
    """
    Admin only — promote a user to admin or demote to user.
    Body: { "username": "sean", "role": "admin" }

    This is how you make someone an admin without hardcoding their username.
    Only existing admins can call this endpoint.
    """
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    data = request.get_json()
    target = (data.get("username") or "").strip().lower()
    new_role = data.get("role", "user")

    if new_role not in ("admin", "user"):
        return jsonify({"error": "Role must be 'admin' or 'user'."}), 400

    users = _load_users()
    if target not in users:
        return jsonify({"error": f"User '{target}' not found."}), 404

    users[target]["role"] = new_role
    _save_users(users)

    return jsonify({
        "message": f"{target} is now {new_role}.",
        "username": target,
        "role": new_role,
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "IT Jobs PH API"}), 200


if __name__ == "__main__":
    print("Starting IT Jobs PH Flask API on http://localhost:5050")
    app.run(port=5050, debug=True)