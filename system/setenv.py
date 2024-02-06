import os
# Import the getsecrets function from the system module
from system.getsecret import getsecrets

# Try retrieving the project_id from Secret Manager
try:
    project_id = getsecrets("project_id", "make-smthng-website")
except:
    # Set the project_id if not found in Secret Manager
    os.environ['GCP_PROJECT'] = "make-smthng-website"
    project_id = os.environ["GCP_PROJECT"]
