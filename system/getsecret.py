import os
import json
import logging
from google.api_core.exceptions import NotFound

try:
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
except ImportError:
    client = None

_config_cache = None


def _load_local_config():
    global _config_cache
    if _config_cache is None:
        try:
            with open('config/config.json') as f:
                _config_cache = json.load(f)
        except Exception as e:
            print(f"[Local Config] Could not load config.json: {e}")
            _config_cache = {}
    return _config_cache


def _load_config_from_secret(secret_name, project_id):
    try:
        resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": resource_name})
        secret_data = response.payload.data.decode("utf-8")
        return json.loads(secret_data)
    except Exception as e:
        print(f"[Secret Config] Failed to load secret '{secret_name}': {e}")
        return {}


def getsecrets(secret_name, project_id=None):
    # Environment overrides make local/test startup deterministic while Cloud
    # Run continues to use Secret Manager by default.
    environment_name = f"PIXELCOUNTER_SECRET_{secret_name.upper().replace('-', '_')}"
    environment_value = os.getenv(environment_name)
    if environment_value is not None:
        return environment_value

    if not project_id:
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')

    secret_value = None

    if client and project_id:
        try:
            resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": resource_name})
            secret_value = response.payload.data.decode('UTF-8').strip()

            if secret_value:
                print(f"[GCP] Retrieved '{secret_name}' from Secret Manager")
                return secret_value
            else:
                print(f"[GCP] Secret '{secret_name}' is empty, trying fallback sources")

        except Exception as e:
            print(f"[GCP] Failed to get '{secret_name}' from Secret Manager: {e}")

        # Try to fetch config.json stored as one secret blob
        try:
            config_data = _load_config_from_secret("sct_config_app", project_id)
            if secret_name in config_data:
                print(f"[GCP] Retrieved '{secret_name}' from sct_config_app secret blob")
                return config_data[secret_name]
        except Exception as e:
            print(f"[GCP] Failed to get '{secret_name}' from sct_config_app secret blob: {e}")

    # --- Fallback to local config ---
    print(f"[Local] Falling back to local config.json for '{secret_name}'")
    local_config = _load_local_config()
    return local_config.get(secret_name, None)


def store_secret(secret_name, secret_value, project_id):
    """Create a Secret Manager secret when needed and add a new version."""
    if not client:
        raise RuntimeError('Google Secret Manager is unavailable')
    if not project_id or not secret_name or secret_value is None:
        raise ValueError('Project, secret name, and value are required')

    parent = f"projects/{project_id}"
    secret_path = f"{parent}/secrets/{secret_name}"
    try:
        client.get_secret(request={'name': secret_path})
    except NotFound:
        client.create_secret(request={
            'parent': parent,
            'secret_id': secret_name,
            'secret': {'replication': {'automatic': {}}},
        })

    response = client.add_secret_version(request={
        'parent': secret_path,
        'payload': {'data': secret_value.encode('utf-8')},
    })
    logging.info("Added a new version for Secret Manager secret '%s'", secret_name)
    return response.name


def store_api_key_in_secrets_manager(api_key, secret_name, project_id):
    """Stores the API key in Google Secrets Manager."""
    parent = f"projects/{project_id}/secrets/{secret_name}"

    try:
        client.create_secret(
            request={
                "parent": f"projects/{project_id}",
                "secret_id": secret_name,
                "secret": {"replication": {"automatic": {}}},
            }
        )
    except Exception as e:
        print(f"Secret {secret_name} already exists or failed to create: {e}")

    client.add_secret_version(
        request={"parent": parent, "payload": {"data": api_key.encode("UTF-8")}}
    )
