# Python standard libraries
import os
import logging
import werkzeug
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
    request
)

# Secrets
import secrets

from flask_wtf.csrf import CSRFProtect

# ProxyFix
from werkzeug.middleware.proxy_fix import ProxyFix

# Markup
from markupsafe import Markup

# crypto
from cryptography.hazmat.primitives import serialization

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

# Generate a nonce (typically done once)
global_nonce = secrets.token_hex(16)

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
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Basic config
app.secret_key = app_secret_key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_PERMANENT'] = True


# Security - cookie/session settings (unique name per app)
app.config['SESSION_COOKIE_NAME'] = os.getenv('SESSION_COOKIE_NAME', 'redirect_appsession')
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

# New Line filter from \n to <br>


def nl2br(value):
    """Converts newlines in a string to HTML line breaks."""
    return Markup(value.replace('\n', '<br>\n'))

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
# API Key
app.register_blueprint(apikeyblue)

# it is necessary to set a password when dealing with OAuth 2.0
app.secret_key = app_secret_key

logging.info("Start processing Function")

# Exempt the API route from CSRF protection
csrf.exempt(pixelcounterblue)


warnings.filterwarnings("ignore", category=UserWarning, module='.*distutils.*')


# Initialize the GCP client using the secure secret value
firestore_client = initialize_gcp_client(project_id)


def get_user_data():
    jwt_token = session.get('jwt_token')
    if jwt_token:
        try:
            decoded_data = jwt.decode(jwt_token,
                                      'secret_key',
                                      algorithms=['HS256'])
            return decoded_data
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    return None


@app.before_request
def before_request():
    g.nonce = global_nonce


# load public key
public_pem = getsecrets("jwt_public_pem", project_id)
public_key = serialization.load_pem_public_key(public_pem.encode())


@app.before_request
def check_jwt():
    token = request.cookies.get("access_token")
    if not token:
        g.user = None
        return

    try:
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="my-api-audience"  # must match `aud` in token
        )
        g.user = decoded
    except jwt.ExpiredSignatureError:
        g.user = None
    except jwt.InvalidTokenError:
        g.user = None


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
@app.errorhandler(werkzeug.exceptions.HTTPException)
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

if __name__ == '__main__':
    if is_prod:
        from waitress import serve
        print("Running with Waitress (Production/QA)...")
        serve(app, host="0.0.0.0", port=port)
    else:
        print("Running in Debug Mode (Dev)...")
        logging.getLogger().setLevel("DEBUG")
        app.run(host='0.0.0.0', port=port, debug=True)
