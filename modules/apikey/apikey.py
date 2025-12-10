# modules/apikey/apikey.py
import secrets
from datetime import datetime
from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, jsonify, current_app
)
import jwt
from modules.auth.auth import login_is_required
from system.firstoredb import apikeys_ref

apikeyblue = Blueprint(
    "apikeyblue",
    __name__,
    template_folder="templates"
)

JWT_SECRET = current_app.config.get("JWT_SECRET", "secret_key") if current_app else "secret_key"


def generate_api_key(length=32):
    """Generate a 12-character hex API key."""
    return secrets.token_hex(length // 2)


def _get_decoded_jwt():
    jwt_token = session.get("jwt_token")
    if not jwt_token:
        return None
    try:
        decoded = jwt.decode(jwt_token, JWT_SECRET, algorithms=["HS256"])
        return decoded
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# --- List & generate page ---
@apikeyblue.route("/apikeys", methods=["GET"])
@login_is_required
def apikey_list():
    decoded = _get_decoded_jwt()
    if not decoded:
        return redirect(url_for("authsblue.login"))

    user_uuid = decoded["uuid"]

    # Query api keys in Firestore
    keys_docs = apikeys_ref.where("user_uuid", "==", user_uuid).stream()
    api_keys = []
    for doc in keys_docs:
        d = doc.to_dict()
        api_keys.append({
            "id": doc.id,
            "api_key": d.get("api_key"),
            "created_at": d.get("created_at"),
            "user_uuid": user_uuid,
            "active": d.get("active", True)
        })

    # Sort descending by created_at if present
    api_keys.sort(key=lambda k: k.get("created_at") or datetime.min, reverse=True)

    # Render list (template will include a meta csrf token)
    return render_template("apikey_list.html", api_keys=api_keys)


# --- Generate new API key (POST) ---
@apikeyblue.route("/generateapikey", methods=["POST", "GET"])
@login_is_required
def generateapikey():
    decoded = _get_decoded_jwt()
    if not decoded:
        return redirect(url_for("authsblue.login"))
    user_uuid = decoded["uuid"]

    # POST to create new key
    if request.method == "POST":
        api_key = generate_api_key()
        now = datetime.utcnow()

        apikeys_ref.document().set({
            "api_key": api_key,
            "created_at": now,
            "user_uuid": user_uuid,
            "active": True
        })

        # Render a small page showing the newly created key (only shown once)
        return render_template("apikey_created.html", api_key=api_key)

    # If GET, redirect to list page
    return redirect(url_for("apikeyblue.apikey_list"))


# --- Toggle active/inactive ---
@apikeyblue.route("/toggle_apikey/<key_id>", methods=["POST"])
@login_is_required
def toggle_apikey(key_id):
    # get logged-in user
    decoded = _get_decoded_jwt()
    if not decoded:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    user_uuid = decoded.get("uuid")

    # get the document reference for this key
    doc_ref = apikeys_ref.document(key_id)
    try:
        doc = doc_ref.get()
    except Exception as e:
        return jsonify({"success": False, "error": f"Firestore error: {e}"}), 500

    if not doc.exists:
        return jsonify({"success": False, "error": "Not found"}), 404

    data = doc.to_dict() or {}

    # optional: ensure only owner (or admin) can toggle
    owner_uuid = data.get("user_uuid")
    # If you have admin role check, add it here. For now only owner can toggle.
    if owner_uuid != user_uuid:
        # If you want admins to toggle, check decoded['role'] etc.
        return jsonify({"success": False, "error": "Forbidden"}), 403

    current = data.get("active", True)
    new_state = not bool(current)

    try:
        # update only the active field and maybe updated_at metadata
        doc_ref.update({
            "active": new_state,
            "updated_at": datetime.utcnow()
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to update: {e}"}), 500

    return jsonify({"success": True, "active": new_state})


# --- Delete key ---
@apikeyblue.route("/delete_apikey/<key_id>", methods=["POST"])
@login_is_required
def delete_apikey(key_id):
    decoded = _get_decoded_jwt()
    if not decoded:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    # Delete the api key directly without ownership check as requested
    try:
        apikeys_ref.document(key_id).delete()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to delete: {e}"}), 500
