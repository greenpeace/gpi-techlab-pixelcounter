# Install Google Libraries
from google.cloud import secretmanager

# Setup the Secret manager Client
client = secretmanager.SecretManagerServiceClient()

def getsecrets(secret_name, project_id):
    resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": resource_name})
        return response.payload.data.decode('UTF-8')
    except:
        return False
