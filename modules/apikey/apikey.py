# modules/apikey/apikey.py
import secrets
import hashlib
from datetime import datetime
from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, jsonify
)
from modules.auth.auth import login_is_required
from modules.auth.auth import admin_required
from system.firstoredb import apikeys_ref, users_ref
from system.jwt_utils import decode_jwt_token

apikeyblue = Blueprint(
    "apikeyblue",
    __name__,
    template_folder="templates"
)

def generate_api_key(length=32):
    """Generate a 12-character hex API key."""
    return secrets.token_hex(length // 2)


def _get_decoded_jwt():
    jwt_token = session.get("jwt_token")
    if not jwt_token:
        return None
    try:
        return decode_jwt_token(jwt_token)
    except Exception:
        return None


# --- List & generate page ---
@apikeyblue.route("/apikeys", methods=["GET"])
@login_is_required
def apikey_list():
    decoded = _get_decoded_jwt()
    if not decoded:
        return redirect(url_for("authsblue.login"))

    user_uuid = decoded["uuid"]
    role = decoded.get("role")

    # Query api keys in Firestore
    if role == "Administrator":
        # Admin sees ALL keys
        keys_docs = apikeys_ref.stream()
        
        # Prefetch user names for mapping (optimize this if thousands of users)
        all_users = users_ref.stream()
        user_map = {}
        for u in all_users:
            u_data = u.to_dict()
            # Construct name
            name_str = f"{u_data.get('given_name','')} {u_data.get('family_name','')}".strip()
            if not name_str: 
                name_str = u_data.get('email', 'Unknown')
            user_map[u_data.get('uuid')] = name_str
            
    else:
        # Regular users see only their own
        keys_docs = apikeys_ref.where("user_uuid", "==", user_uuid).stream()
        user_map = {} # No need to map others
        
    api_keys = []
    for doc in keys_docs:
        d = doc.to_dict()
        owner_uuid = d.get("user_uuid")
        
        # Determine display name
        display_name = "Me"
        if role == "Administrator":
             display_name = user_map.get(owner_uuid, "Unknown User")
             
        api_keys.append({
            "id": doc.id,
            "api_key": (
                f"{d.get('key_prefix') or d.get('api_key_prefix', '')}..." if d.get('api_key_hash')
                else f"{d.get('api_key', '')[:6]}...{d.get('api_key', '')[-4:]}"
            ),
            "created_at": d.get("created_at"),
            "user_uuid": owner_uuid,
            "user_name": display_name,
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
        owner_name = decoded.get('name') or decoded.get('email') or 'API user'

        apikeys_ref.document().set({
            "api_key_hash": hashlib.sha256(api_key.encode('utf-8')).hexdigest(),
            "key_prefix": api_key[:6],
            "created_at": now,
            "user_uuid": user_uuid,
            "owner_name": owner_name,
            "owner_email": decoded.get('email', ''),
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
    if owner_uuid != user_uuid and decoded.get('role') != 'Administrator':
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

    try:
        doc_ref = apikeys_ref.document(key_id)
        doc = doc_ref.get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Not found"}), 404
        data = doc.to_dict() or {}
        if decoded.get('role') != 'Administrator' and data.get('user_uuid') != decoded.get('uuid'):
            return jsonify({"success": False, "error": "Forbidden"}), 403
        doc_ref.delete()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to delete: {e}"}), 500
