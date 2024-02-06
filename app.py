# Python standard libraries
import os
import logging
import werkzeug
from werkzeug.exceptions import abort

# Third-party libraries
from flask import Flask, render_template

# Markup
from markupsafe import Markup

# Internal imports
from system.getsecret import getsecrets
from system.gcpclientinit import initialize_gcp_client

# Import project id
from system.setenv import project_id
# Initialize the GCP client using the secure secret value
#firestore_client = initialize_gcp_client(project_id)

# Get the secret for Service Account
app_secret_key = getsecrets("app_secret_key",project_id)

# Create the Flask application error handlers
def page_not_found(e):
  return render_template('systemmsg/404.html'), 404

def internal_server_error(e):
  return render_template('systemmsg/500.html'), 500

# Initialize Flask App
app = Flask(__name__)

# Logging server calls
app.logger.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s:%(message)s')

# New Line filter from \n to <br>
def nl2br(value):
    """Converts newlines in a string to HTML line breaks."""
    return Markup(value.replace('\n', '<br>\n'))

# register frontpage
from modules.frontpage.frontpage import frontpageblue
app.register_blueprint(frontpageblue)
# Register AUTh Module
from modules.auth.auth import authsblue
app.register_blueprint(authsblue)
# Register AUTh Module
from modules.pixelcounter.pixelcounter import pixelcounterblue
app.register_blueprint(pixelcounterblue)
# Dashboard
from modules.dashboard.dashboard import dashboardblue
app.register_blueprint(dashboardblue)
# qrcode
from modules.qrcode.qrcode import qrcodeblue
app.register_blueprint(qrcodeblue)
# url shortner
from modules.urlshortner.urlshortner import urlshortnerblue
app.register_blueprint(urlshortnerblue)

#it is necessary to set a password when dealing with OAuth 2.0
app.secret_key = app_secret_key

logging.info("Start processing Function")

#
# 404 Page not found    
#
@app.errorhandler(404)
def not_found_error(error):
    logging.info(f'404 Page Not Found')
    return render_template('404.html'), 404

#
# 500 error trying to access the API endpoint
#
@app.errorhandler(werkzeug.exceptions.HTTPException)
def internal_error(error):
    logging.info(f'500 System Error')
    return render_template('500.html'), 500
  
@app.route('/favicon.ico')
def favicon():
    return ''

#    
# Setting up to serve on port 8080
#
port = int(os.environ.get('PORT', 8080))
if __name__ == '__main__':
    from waitress import serve
    serve(app, host="0.0.0.0", port=port)
