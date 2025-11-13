import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, jsonify
from modules.auth.auth import require_valid_api_key  # Replace with your actual module path


@pytest.fixture
def app():
    app = Flask(__name__)

    @app.route("/protected")
    @require_valid_api_key
    def protected():
        return jsonify({"message": "Access granted"})

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


@patch("your_module.users_ref")
def test_missing_api_key(mock_users_ref, app):
    client = app.test_client()
    resp = client.get("/protected")
    assert resp.status_code == 403
    assert "Missing API key" in resp.get_data(as_text=True)


@patch("your_module.users_ref")
def test_valid_active_api_key(mock_users_ref, app):
    mock_users_ref.stream.return_value = mock_firestore_user({"api_key": "key123", "status": "active"})
    client = app.test_client()
    resp = client.get("/protected?apikey=key123")
    assert resp.status_code == 200
    assert "Access granted" in resp.get_data(as_text=True)


@patch("your_module.users_ref")
def test_inactive_api_key(mock_users_ref, app):
    mock_users_ref.stream.return_value = mock_firestore_user({"api_key": "key123", "status": "inactive"})
    client = app.test_client()
    resp = client.get("/protected?apikey=key123")
    assert resp.status_code == 403
    assert "API key inactive" in resp.get_data(as_text=True)


@patch("your_module.users_ref")
def test_api_key_not_found(mock_users_ref, app):
    # No user returns the key
    mock_users_ref.stream.return_value = []
    client = app.test_client()
    resp = client.get("/protected?apikey=notfound")
    assert resp.status_code == 403
    assert "API key not found" in resp.get_data(as_text=True)


@patch("your_module.users_ref", side_effect=Exception("Firestore error"))
def test_firestore_error(mock_users_ref, app):
    client = app.test_client()
    resp = client.get("/protected?apikey=key123")
    assert resp.status_code == 500
    assert "Firestore error" in resp.get_data(as_text=True)
