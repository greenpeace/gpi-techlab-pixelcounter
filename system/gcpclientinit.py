from googleapiclient.discovery import build
from google.oauth2 import service_account
from system.getsecret import getsecrets
import json

def initialize_gcp_client(project_id):
    # Retrieve the secret value from Secret Manager
    secret_value = getsecrets(secret_name="service_account-key", project_id=project_id)

    # Create a Google OAuth2 service account object
    if secret_value:
        credentials = service_account.Credentials.from_service_account_info(json.loads(secret_value))
    else:
        raise ValueError("Failed to retrieve secret value from Secret Manager")

    # Create a service account client
    return build('firestore', 'v1', credentials=credentials)
