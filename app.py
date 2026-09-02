# Python standard libraries
import os
import logging
import jwt
import babel
from datetime import datetime, timedelta

# Third-party libraries
from flask import (
    Flask,
    render_template,
    g,
    session,
    send_file,
)

# Secrets
import secrets

from flask_wtf.csrf import CSRFProtect

# ProxyFix
from werkzeug.middleware.proxy_fix import ProxyFix

# Internal imports
from system.getsecret import getsecrets
from system.gcpclientinit import initialize_gcp_client
# Install Google Libraries
import google.cloud.logging
# Warnings
import warnings
# Import project id
from system.setenv import project_id
# Import Modules
from modules.frontpage.frontpage import frontpageblue
from modules.auth.auth import authsblue
from modules.pixelcounter.pixelcounter import pixelcounterblue
from modules.dashboard.dashboard import dashboardblue
from modules.qrcode.qrcode import qrcodeblue
from modules.urlshortner.urlshortner import urlshortnerblue
from modules.apikey.apikey import apikeyblue
# Import Users
from modules.users.users import usersblue, get_login_config
from modules.users.profile import profileblue
# Import NRO
from modules.nro.nro import nroblue

# Initialize the GCP client using the secure secret value
client = google.cloud.logging.Client()
logger = client.logger('Pixelcounter')

# Get the secret for Service Account
app_secret_key = getsecrets("app_secret_key", project_id)


# Create the Flask application error handlers
def page_not_found(e):
    return render_template('systemmsg/404.html'), 404


def internal_server_error(e):
    return render_template('systemmsg/500.html'), 500


# Initialize Flask App
app = Flask(__name__)

is_production = os.getenv('IS_PRODUCTION', 'false').lower() == 'true'

# Trust proxy headers from Cloud Run for HTTPS and Host info
if is_production:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Basic config
app.secret_key = app_secret_key
app.config['JWT_SECRET'] = app_secret_key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_PERMANENT'] = True


# Security - cookie/session settings (unique name per app)
app.config['SESSION_COOKIE_NAME'] = os.getenv('SESSION_COOKIE_NAME', 'pixelcounter_session')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('IS_PRODUCTION', 'false').lower() == 'true'
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if app.config['SESSION_COOKIE_SECURE'] else 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True


# CSRF protection
csrf = CSRFProtect(app)

# Make get_login_config available in all templates
app.jinja_env.globals.update(get_login_config=get_login_config)


# Logging server calls
app.logger.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s:%(message)s')


# Configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)


@app.template_filter()
def format_datetime(value, format='medium'):
    if format == 'full':
        format = "EEEE, y MMMM d. 'at' HH:mm"
    elif format == 'medium':
        format = "EE y-MM-dd"
    elif format == 'blog':
        format = "EE dd y"

    return babel.dates.format_datetime(value, format)

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
# Users
app.register_blueprint(usersblue)
app.register_blueprint(profileblue)
# API Key
# API Key
app.register_blueprint(apikeyblue)
# NRO
app.register_blueprint(nroblue)

# it is necessary to set a password when dealing with OAuth 2.0
app.secret_key = app_secret_key

logging.info("Start processing Function")

# Only public/machine endpoints are exempt from browser CSRF checks.
for endpoint in (
    'pixelcounterblue.create_counter',
    'pixelcounterblue.count_pixel',
    'pixelcounterblue.counter',
    'pixelcounterblue.count',
):
    csrf.exempt(app.view_functions[endpoint])


warnings.filterwarnings("ignore", category=UserWarning, module='.*distutils.*')


# Initialize the GCP client using the secure secret value
firestore_client = initialize_gcp_client(project_id)


def get_user_data():
    jwt_token = session.get('jwt_token')
    if jwt_token:
        try:
            from system.jwt_utils import decode_jwt_token
            decoded_data = decode_jwt_token(jwt_token)
            return decoded_data
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    return None


@app.before_request
def before_request():
    g.nonce = secrets.token_urlsafe(24)


@app.context_processor
def inject_nonce():
    return {'nonce': g.get('nonce', '')}


@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://storage.googleapis.com https://*.googleusercontent.com; "
        "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'"
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if is_production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.context_processor
def inject_now():
    return {'now': datetime.now}


@app.context_processor
def inject_user_data():
    user_data = get_user_data()
    return {'user_data': user_data}


# For progressive web app (PWA)
@app.route('/manifest.json')
def serve_manifest():
    return send_file('manifest.json', mimetype='application/manifest+json')

# progressive web app (PWA)


@app.route('/sw.js')
def serve_sw():
    return send_file('sw.js', mimetype='application/javascript')


#
# 404 Page not found
#
@app.errorhandler(404)
def not_found_error(error):
    logging.info('404 Page Not Found')
    return render_template('404.html'), 404


#
# 500 error trying to access the API endpoint
#
@app.errorhandler(500)
def internal_error(error):
    logging.info('500 System Error')
    return render_template('500.html'), 500


@app.route('/favicon.ico')
def favicon():
    return ''


#
# Setting up to serve on port 8080
#
port = int(os.environ.get('PORT', 8080))
is_prod = os.environ.get('IS_PRODUCTION', 'false').lower() == 'true'

# ----------------------------
# MAIN (LOCAL ONLY)
# ----------------------------
if __name__ == "__main__":
    # ONLY used for local dev
    app.run(host="127.0.0.1", port=port, debug=not is_prod)
