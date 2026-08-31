# Get the Flask Files Required
import os
from flask import (
    Blueprint,
    session,
    request,
    redirect,
    abort,
    url_for,
    flash,
    jsonify,
    render_template
)
import requests
import json
import random
import string
import uuid
import jwt
import logging
import time
from datetime import datetime, timedelta
import urllib.parse

# Get Google Login with oauth
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from pip._vendor import cachecontrol

from functools import wraps

from system.firstoredb import users_ref, apikeys_ref
from system.jwt_utils import generate_jwt_token
from system.getsecret import getsecrets
# Import project id
from system.setenv import project_id

authsblue = Blueprint('authsblue', __name__)

# Get the secrets for authentication
client_secret = getsecrets("client_secret_key", project_id)
app_secret_key = getsecrets("app_secret_key", project_id)
restrciteddomain = getsecrets("restrciteddomain", project_id)

# Okta configuration
okta_client_id = getsecrets("okta_client_id", project_id)
okta_client_secret = getsecrets("okta_client_secret", project_id)
okta_issuer = getsecrets("okta_issuer", project_id)

odc_client_id = getsecrets("odc_client_id", project_id)
odc_client_secret = getsecrets("odc_client_secret", project_id)
odc_issuer = getsecrets("odc_issuer", project_id)

# Retrieve the secret values for Google OAuth
secret_value = getsecrets("client_secret_file", project_id)
client_secret_dict = json.loads(secret_value)

scopes = ["https://www.googleapis.com/auth/userinfo.profile",
          "https://www.googleapis.com/auth/userinfo.email",
          "openid"]

is_production = os.getenv('IS_PRODUCTION', 'false').lower() == 'true'

# if not is_production:
#    # this is to set our environment to https because OAuth 2.0
#    # only supports https environments
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# enter your client id you got from Google console

GOOGLE_CLIENT_ID = client_secret

# for test environment - https://pixelcounter-test-170392023448.europe-north1.run.app/callback
# for prod environment - https://counter.greenpeace.org/callback
redirect_uri = (
    "https://counter.greenpeace.org/callback" if is_production else
    "http://127.0.0.1:8080/callback"
)

# Flow is OAuth 2.0 a class that stores all the information on
# how we want to authorize our users
# Use the production redirect_uri if it's set
flow = Flow.from_client_config(
    client_config=client_secret_dict,
    scopes=scopes,
    redirect_uri=redirect_uri
)


#
# API Route Default displays a webpage
#
@authsblue.route("/login")
def login():
    return render_template('login.html', **locals())


#
# the logout page and function
#
@authsblue.route("/logout")
def logout():
    session.clear()
    return redirect("/")


#
# API Route Default displays a webpage
#
@authsblue.route("/loginseq")
def loginseq():
    # asking the flow class for the authorization (login) url
    authorization_url, state = flow.authorization_url()
    session.permanent = True
    session['state'] = state
    return redirect(authorization_url)

# Okta login route
@authsblue.route("/oktalogin")
def oktalogin():
    # Fetch latest Okta secrets
    dynamic_okta_client_id = getsecrets("okta_client_id", project_id)
    dynamic_okta_issuer = getsecrets("okta_issuer", project_id)
    
    if not dynamic_okta_client_id or not dynamic_okta_issuer:
        flash("Okta authentication is not fully configured. Please contact an administrator.")
        return redirect(url_for("authsblue.login"))

    # Build Okta authorization URL
    params = {
        "client_id": dynamic_okta_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": url_for("authsblue.oktacallback", _external=True),
        "state": uuid.uuid4().hex
    }
    session["okta_state"] = params["state"]
    # Build authorize URL from okta_issuer
    base_url = dynamic_okta_issuer.rstrip('/')
    if '/oauth2' not in base_url:
        authorize_url = f"{base_url}/oauth2/v1/authorize"
    else:
        authorize_url = f"{base_url}/v1/authorize"
        
    request_url = f"{authorize_url}?{urllib.parse.urlencode(params)}"
    return redirect(request_url)


@authsblue.route("/oktacallback")
def oktacallback():
    # Exchange code for token
    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("okta_state"):
        abort(403)

    # Fetch latest Okta secrets for token exchange
    dynamic_okta_client_id = getsecrets("okta_client_id", project_id)
    dynamic_okta_client_secret = getsecrets("okta_client_secret", project_id)
    dynamic_okta_issuer = getsecrets("okta_issuer", project_id)

    base_url = dynamic_okta_issuer.rstrip('/')
    if '/oauth2' not in base_url:
        token_url = f"{base_url}/oauth2/v1/token"
    else:
        token_url = f"{base_url}/v1/token"
    auth = (dynamic_okta_client_id, dynamic_okta_client_secret)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": url_for("authsblue.oktacallback", _external=True)
    }
    response = requests.post(token_url, data=data, auth=auth)
    token_data = response.json()

    id_token_jwt = token_data.get("id_token")
    if not id_token_jwt:
        flash("Failed to login with Okta")
        return redirect(url_for("authsblue.login"))

    # Decode ID token (simplified for now, ideally verify RS256 with Okta jwks)
    decoded_token = jwt.decode(id_token_jwt, options={"verify_signature": False})

    # Map Okta claims to id_info style
    id_info = {
        'sub': decoded_token.get('sub'),
        'email': decoded_token.get('email'),
        'name': decoded_token.get('name'),
        'picture': decoded_token.get('picture'),
        'locale': decoded_token.get('locale', 'en')
    }

    # Verification of domain
    email = id_info.get("email") or ""
    domain = email.split('@')[-1].strip().lower() if '@' in email else ""
    allowed_domains = ['gp-test.org']
    if restrciteddomain:
        allowed_domains.append(str(restrciteddomain).strip().lower())
        
    logging.info(f"Checking Okta auth for email: {email}. Allowed domains: {allowed_domains}")
        
    if not email or domain not in allowed_domains:
        flash(f'Your email domain ({domain}) is not authorized. Allowed: {", ".join(allowed_domains)}')
        return redirect(url_for('frontpageblue.index'))

    # Ensure 'sub' is present to prevent Firestore lookup crashes
    if not id_info.get('sub'):
        logging.error("Okta ID Token missing 'sub' (User ID) claim!")
        flash("Okta authentication failed: Missing user ID.")
        return redirect(url_for('authsblue.login'))

    # Check if the user exists in Firestore
    user_doc_ref = users_ref.document(id_info['sub'])
    user_data = user_doc_ref.get().to_dict()

    if not user_data:
        user_data = create_new_user(id_info)
    else:
        user_doc_ref.update({'lastLoginAt': datetime.now()})

    # Generate JWT token
    user_jwt_data = {
        'google_id': id_info['sub'],
        'name': user_data['name'],
        'photo': user_data.get('avatar', ''),
        'email': user_data['email'],
        'uuid': user_data.get('uuid'),
        'customer_id': user_data['customer_id'],
        'role': user_data['role'],
        'groups': user_data.get('groups', []),
        'language': user_data.get('language')
    }
    jwt_token = generate_jwt_token(user_jwt_data)
    session['jwt_token'] = jwt_token
    session['email'] = user_data['email']
    session['role'] = user_data["role"]
    
    return redirect(url_for('dashboardblue.main'))


@authsblue.route("/odclogin")
def odclogin():
    # Build ODC authorization URL
    params = {
        "client_id": odc_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": url_for("authsblue.odccallback", _external=True),
        "state": uuid.uuid4().hex
    }
    session["odc_state"] = params["state"]
    authorize_url = f"{odc_issuer.rstrip('/')}/v1/authorize"
    request_url = f"{authorize_url}?{urllib.parse.urlencode(params)}"
    return redirect(request_url)


@authsblue.route("/odccallback")
def odccallback():
    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("odc_state"):
        abort(403)

    token_url = f"{odc_issuer.rstrip('/')}/v1/token"
    auth = (odc_client_id, odc_client_secret)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": url_for("authsblue.odccallback", _external=True)
    }
    response = requests.post(token_url, data=data, auth=auth)
    token_data = response.json()

    id_token_jwt = token_data.get("id_token")
    if not id_token_jwt:
        flash("Failed to login with ODC")
        return redirect(url_for("authsblue.login"))

    decoded_token = jwt.decode(id_token_jwt, options={"verify_signature": False})

    id_info = {
        'sub': decoded_token.get('sub'),
        'email': decoded_token.get('email'),
        'name': decoded_token.get('name'),
        'picture': decoded_token.get('picture'),
        'locale': decoded_token.get('locale', 'en')
    }

    email = id_info.get("email") or ""
    domain = email.split('@')[-1].strip().lower() if '@' in email else ""
    allowed_domains = ['gp-test.org']
    if restrciteddomain:
        allowed_domains.append(str(restrciteddomain).strip().lower())
        
    if not email or domain not in allowed_domains:
        flash(f'Your email domain ({domain}) is not authorized. Allowed: {", ".join(allowed_domains)}')
        return redirect(url_for('frontpageblue.index'))

    user_doc_ref = users_ref.document(id_info['sub'])
    user_data = user_doc_ref.get().to_dict()

    if not user_data:
        user_data = create_new_user(id_info)
    else:
        user_doc_ref.update({'lastLoginAt': datetime.now()})

    user_jwt_data = {
        'google_id': id_info['sub'],
        'name': user_data['name'],
        'photo': user_data.get('avatar', ''),
        'email': user_data['email'],
        'uuid': user_data.get('uuid'),
        'customer_id': user_data['customer_id'],
        'role': user_data['role'],
        'groups': user_data.get('groups', []),
        'language': user_data.get('language')
    }
    jwt_token = generate_jwt_token(user_jwt_data)
    session['jwt_token'] = jwt_token
    session['email'] = user_data['email']
    session['role'] = user_data["role"]
    
    return redirect(url_for('dashboardblue.main'))

    if not user_data.get("role"):
        flash("Your account is not yet assigned a role. Please contact an administrator.")
        return render_template("unauthorized.html")

    # Generate user data for JWT token
    user_jwt_data = {
        'google_id': id_info.get("sub"),
        'name': id_info.get("name"),
        'photo': id_info.get("picture"),
        'email': id_info.get("email"),
        'uuid': user_data["uuid"],
        'customer_id': user_data["customer_id"],
        'role': user_data["role"],
        'groups': user_data.get('groups', []),
        'language': id_info.get("locale")
    }

    # Generate JWT token
    jwt_token = generate_jwt_token(user_jwt_data)

    # Store JWT token in session
    session['jwt_token'] = jwt_token
    session['role'] = user_data["role"]

    return redirect(url_for('dashboardblue.main'))


@authsblue.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if session.get("state") != request.args.get("state"):
        logging.info("Callback route not reached!")
        abort(500)  # State does not match!

    # Remove the state from the session
    session.pop("state", None)

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    # the final page where the authorized users will end up
    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    #
    # This code is to limit the login to a specific domain
    #
    email = id_info.get("email")
    if email.split('@')[1] != restrciteddomain:
        flash('You are not allowed to login to this site!')
        return redirect(url_for('frontpageblue.index'))

    # Check if the user exists in Firestore
    users_data = users_ref.document(id_info['sub'])
    user_data = users_data.get().to_dict()

    if not user_data:
        user_data = create_new_user(id_info)
    else:
        # User exists, update the lastLoginAt field
        user_doc_ref = users_ref.document(id_info['sub'])
        user_doc_ref.update({
            'lastLoginAt': datetime.now()
        })

    # Generate user data for JWT token
    user_jwt_data = {
        'google_id': id_info.get("sub"),
        'name': id_info.get("name"),
        'photo': id_info.get("picture"),
        'email': id_info.get("email"),
        'uuid': user_data["uuid"],
        'customer_id': user_data["customer_id"],
        'role': user_data["role"],
        'language': id_info.get("locale")
    }

    # Generate JWT token
    jwt_token = generate_jwt_token(user_jwt_data)

    # Store JWT token in session
    session['jwt_token'] = jwt_token
    session['role'] = user_data["role"]

    return redirect(url_for('dashboardblue.main'))


RATE_LIMIT = 5
RATE_WINDOW = 60
rate_cache = {}


def rate_limit(limit=RATE_LIMIT, window=RATE_WINDOW):
    def decorator(func):
        @wraps(func)  # preserves original function name
        def _rate_limiter(*args, **kwargs):  # unique inner name
            ip = request.remote_addr
            now = time.time()
            history = [t for t in rate_cache.get(ip, []) if now - t < window]
            if len(history) >= limit:
                return jsonify({"error": "Too many requests"}), 429
            history.append(now)
            rate_cache[ip] = history
            return func(*args, **kwargs)
        return _rate_limiter
    return decorator


# a function to check if the user is authorized or not
def login_is_required(func):
    @wraps(func)
    def _login_wrapper(*args, **kwargs):
        jwt_token = session.get('jwt_token')

        if not jwt_token:
            # Redirect to logout if JWT token is not present
            return redirect(url_for('authsblue.logout'))

        try:
            decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])
            user_id = decoded_data.get('google_id')
        except jwt.ExpiredSignatureError:
            # Handle expired token
            return redirect(url_for('authsblue.logout'))
        except jwt.InvalidTokenError:
            # Handle invalid token
            return redirect(url_for('authsblue.logout'))

        if not user_id:
            # Redirect to logout if user ID is not present in the token
            return redirect(url_for('authsblue.logout'))

        # Update the last_activity_time in the session on every request
        session['last_activity_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Call the original function
        return func(*args, **kwargs)

    return _login_wrapper


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        jwt_token = session.get('jwt_token')
        if not jwt_token:
            return redirect(url_for('authsblue.logout'))

        try:
            decoded = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])
            if decoded.get('role') != 'Administrator':
                flash('Admins only!')
                return redirect(url_for('frontpageblue.index'))
        except jwt.ExpiredSignatureError:
            return redirect(url_for('authsblue.logout'))
        except jwt.InvalidTokenError:
            return redirect(url_for('authsblue.logout'))

        return f(*args, **kwargs)
    return decorated_function


def validate_api_key(provided_api_key):
    """Validate an API key from the top-level apikeys collection."""
    if not provided_api_key:
        return False, "Missing API key"

    # Query Firestore for matching key
    docs = apikeys_ref.where("api_key", "==", provided_api_key).limit(1).get()
    if not docs:
        return False, "API key not found"

    key_data = docs[0].to_dict()

    if not key_data.get("active", False):
        return False, "API key inactive"

    return True, None


def require_valid_api_key(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return '', 200

        provided_api_key = request.args.get("apikey") or request.headers.get("X-API-Key")

        # Pass the users_ref to the helper
        valid, reason = validate_api_key(provided_api_key)

        if not valid:
            return jsonify({"error": "Unauthorized access", "reason": reason}), 403

        return function(*args, **kwargs)
    return wrapper


def logout_inactive_users():
    last_activity_time_str = session.get('last_activity_time')
    if last_activity_time_str:
        last_activity_time = datetime.strptime(last_activity_time_str, "%Y-%m-%d %H:%M:%S")
        time_since_activity = datetime.now() - last_activity_time
        if time_since_activity > timedelta(minutes=30):
            session.clear()
            return redirect(url_for('authsblue.logout'))


@authsblue.before_request
def before_request():
    logout_inactive_users()


@authsblue.after_request
def after_request(response):
    session['last_activity_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return response


# Decode and verify JWT token
def decode_jwt_token(token):
    try:
        decoded_data = jwt.decode(
            token,
            'secret_key',
            algorithms=['HS256'],
            options={
                'verify_exp': True,
                'leeway': 60  # Add 60 seconds of leeway for clock skew
            }
        )
        return decoded_data
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# Function to retrieve user data from JWT token
def get_user_data_from_token():
    jwt_token = session.get('jwt_token')
    if jwt_token:
        user_data = decode_jwt_token(jwt_token)
        return user_data
    return None


# Create a cuctomer_id
def generate_customer_id(length=8):
    characters = string.ascii_letters + string.digits
    customer_id = ''.join(random.choice(characters) for _ in range(length))
    return customer_id


# create a user
def create_new_user(id_info, groups=None, permissions=None):
    # Generate customer ID
    customer_id = generate_customer_id()

    # Get the current timestamp
    current_time = datetime.now()

    # Generate a version 4 UUID
    uuid_value = uuid.uuid4()

    # Convert the UUID to a string
    uuid_str = str(uuid_value)

    # Create a new user entry in Firestore
    user_data = {
        'name': id_info.get("name"),
        'given_name': id_info.get("given_name"),
        'family_name': id_info.get("family_name"),
        'email': id_info.get("email"),
        'customer_id': customer_id,
        'avatar': '',
        'createdAt': current_time,
        'lastLoginAt': current_time,
        'phone': '',
        'role': 'Admin',
        'permissions': permissions if permissions else [],
        'groups': groups if groups else [],
        'disabled': False,
        'uuid': uuid_str
    }
    users_ref.document(id_info['sub']).set(user_data)

    return user_data
