import os
# configure local or cloud
try:
    # Get the sites environment credentials
    project_id = os.environ["GCP_PROJECT"]
except Exception as e:
    # Set Local Environment Variables (Local)
    print(e)
    # Set Local Environment Variables (Local)
    os.environ['GCP_PROJECT'] = 'make-smthng-website'
    # Get project id to intiate
    project_id = os.environ["GCP_PROJECT"]
