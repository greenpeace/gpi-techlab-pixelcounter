# Python standard libraries
import os
import logging
import werkzeug
from werkzeug.exceptions import abort

# Third-party libraries
from flask import Flask, render_template

# Internal imports
from system.getsecret import getsecrets

# Import Modules
# Import Authorization
from modules.auth.auth import authsblue
# Import pixelcounterblue
from modules.pixelcounter.pixelcounter import pixelcounterblue
# Import from Dashboard
from modules.dashboard.dashboard import dashboardblue
# Import Frontpage
from modules.frontpage.frontpage import frontpageblue
# from qrcode
from modules.qrcode.qrcode import qrcodeblue
# from qrcode
from modules.urlshortner.urlshortner import urlshortnerblue

# Import project id
from system.setenv import project_id

# Get the secret for Service Account
app_secret_key = getsecrets("app_secret_key",project_id)

# Create the Flask application error handlers
def page_not_found(e):
  return render_template('systemmsg/404.html'), 404

def internal_server_error(e):
  return render_template('systemmsg/500.html'), 500

# Initialize Flask App
app = Flask(__name__)

# register frontpage
app.register_blueprint(frontpageblue)
# Register AUTh Module
app.register_blueprint(authsblue)
# Register AUTh Module
app.register_blueprint(pixelcounterblue)
# Dashboard
app.register_blueprint(dashboardblue)
# qrcode
app.register_blueprint(qrcodeblue)
# url shortner
app.register_blueprint(urlshortnerblue)

#it is necessary to set a password when dealing with OAuth 2.0
app.secret_key = app_secret_key

logging.info("Start processing Function")

# Register Error Handlers
app.register_error_handler(404, page_not_found)
app.register_error_handler(500, internal_server_error)

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

#
# Setting up to serve on port 8080
#
port = int(os.environ.get('PORT', 8080))
if __name__ == '__main__':
    from waitress import serve
    serve(app, host="0.0.0.0", port=port)
