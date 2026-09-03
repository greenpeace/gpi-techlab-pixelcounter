import hashlib
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, g, jsonify
from modules.auth.auth import require_valid_api_key  # Replace with your actual module path


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.route("/protected")
    @require_valid_api_key
    def protected():
        return jsonify({"message": "Access granted", "actor": g.api_key_owner})

    return app


def mock_firestore_user(api_key_data):
    """Helper to mock Firestore structure."""
    user_mock = MagicMock()
    api_key_doc = MagicMock()
    api_key_doc.to_dict.return_value = api_key_data

    # Subcollection mock
    keys_ref_mock = MagicMock()
    keys_ref_mock.where.return_value.get.return_value = [api_key_doc]

    # Each user has an 'api_keys' subcollection
    user_mock.reference.collection.return_value = keys_ref_mock
    return [user_mock]


@patch("modules.auth.auth.apikeys_ref")
def test_missing_api_key(mock_apikeys_ref, app):
    client = app.test_client()
    resp = client.get("/protected")
    assert resp.status_code == 403
    assert "Missing API key" in resp.get_data(as_text=True)


@patch("modules.auth.auth.apikeys_ref")
def test_valid_active_api_key(mock_apikeys_ref, app):
    api_key_doc = MagicMock()
    api_key_doc.to_dict.return_value = {"api_key": "key123", "active": True}
    mock_apikeys_ref.where.return_value.limit.return_value.get.return_value = [api_key_doc]
    
    client = app.test_client()
    resp = client.get("/protected", headers={"X-API-Key": "key123"})
    assert resp.status_code == 200
    assert "Access granted" in resp.get_data(as_text=True)


@patch("modules.auth.auth.users_ref")
@patch("modules.auth.auth.apikeys_ref")
def test_api_key_activity_actor_resolves_to_owner_email(mock_apikeys_ref, mock_users_ref, app):
    api_key_doc = MagicMock()
    api_key_doc.to_dict.return_value = {
        "api_key_hash": hashlib.sha256(b"key123").hexdigest(),
        "key_prefix": "key123",
        "user_uuid": "user-uuid",
        "active": True,
    }
    mock_apikeys_ref.where.return_value.limit.return_value.get.return_value = [api_key_doc]
    user_doc = MagicMock()
    user_doc.to_dict.return_value = {"email": "owner@example.org"}
    mock_users_ref.where.return_value.limit.return_value.get.return_value = [user_doc]

    resp = app.test_client().get("/protected", headers={"X-API-Key": "key123"})

    assert resp.status_code == 200
    assert resp.get_json()["actor"] == "owner@example.org"


@patch("modules.auth.auth.apikeys_ref")
def test_inactive_api_key(mock_apikeys_ref, app):
    api_key_doc = MagicMock()
    api_key_doc.to_dict.return_value = {"api_key": "key123", "active": False}
    mock_apikeys_ref.where.return_value.limit.return_value.get.return_value = [api_key_doc]
    
    client = app.test_client()
    resp = client.get("/protected", headers={"X-API-Key": "key123"})
    assert resp.status_code == 403
    assert "API key inactive" in resp.get_data(as_text=True)


@patch("modules.auth.auth.apikeys_ref")
def test_api_key_not_found(mock_apikeys_ref, app):
    mock_apikeys_ref.where.return_value.limit.return_value.get.return_value = []
    
    client = app.test_client()
    resp = client.get("/protected", headers={"X-API-Key": "notfound"})
    assert resp.status_code == 403
    assert "API key not found" in resp.get_data(as_text=True)


@patch("modules.auth.auth.apikeys_ref")
def test_firestore_error(mock_apikeys_ref, app):
    mock_apikeys_ref.where.side_effect = Exception("Firestore error")
    
    client = app.test_client()
    with pytest.raises(Exception, match="Firestore error"):
        client.get("/protected", headers={"X-API-Key": "key123"})
