from googleapiclient.discovery import build
from google.oauth2 import service_account
from system.getsecret import getsecrets
import json


def initialize_gcp_client(project_id):
    # Retrieve the secret value from Secret Manager
    secret_value = getsecrets(secret_name="service-account-key",
                              project_id=project_id)

    if not secret_value:
        raise ValueError("Failed to retrieve secret value from Secret Manager")

    # Create a Google OAuth2 service account object
    credentials_info = json.loads(secret_value)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)

    # Specify the necessary scopes
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    # Create a service account client
    scoped_credentials = credentials.with_scopes(scopes)
    client = build('firestore', 'v1', credentials=scoped_credentials)

    # Clean up the secret from memory
    del credentials_info, secret_value

    return client