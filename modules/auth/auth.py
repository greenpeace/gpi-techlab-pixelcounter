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
    render_template,
    g,
)
import hashlib
from google.cloud import firestore
import requests
import json
import secrets
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

from system.firstoredb import db, users_ref, apikeys_ref, rate_limit_ref
from system.jwt_utils import decode_jwt_token as decode_internal_jwt_token, generate_jwt_token
from system.getsecret import getsecrets
# Import project id
from system.setenv import project_id

authsblue = Blueprint('authsblue', __name__)


def _load_or_create_user(id_info):
    """Load an IdP user, linking an administrator-preprovisioned email record."""
    subject = id_info.get('sub')
    user_doc_ref = users_ref.document(subject)
    snapshot = user_doc_ref.get()
    if snapshot.exists:
        user_doc_ref.update({'lastLoginAt': datetime.now()})
        return snapshot.to_dict() or {}

    email = (id_info.get('email') or '').strip().lower()
    matches = users_ref.where('email', '==', email).limit(1).get() if email else []
    if matches:
        existing = matches[0]
        user_data = existing.to_dict() or {}
        user_data['lastLoginAt'] = datetime.now()
        user_doc_ref.set(user_data)
        if existing.id != subject:
            existing.reference.delete()
        return user_data

    return create_new_user(id_info)

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
if not is_production:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


def _verify_oidc_token(encoded_token, issuer, audience, expected_nonce):
    """Verify an OIDC ID token against the configured provider's signing keys."""
    issuer = issuer.rstrip('/')
    if not issuer.startswith('https://'):
        raise jwt.InvalidIssuerError('OIDC issuer must use HTTPS')
    if not expected_nonce:
        raise jwt.InvalidTokenError('OIDC nonce is missing from the session')
    jwks_uri = (
        f"{issuer}/v1/keys" if '/oauth2' in issuer
        else f"{issuer}/oauth2/v1/keys"
    )
    signing_key = jwt.PyJWKClient(jwks_uri).get_signing_key_from_jwt(encoded_token)
    claims = jwt.decode(
        encoded_token,
        signing_key.key,
        algorithms=['RS256'],
        audience=audience,
        issuer=issuer,
        options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']},
    )
    if not secrets.compare_digest(str(claims.get('nonce', '')), str(expected_nonce)):
        raise jwt.InvalidTokenError('OIDC nonce mismatch')
    return claims

# enter your client id you got from Google console

GOOGLE_CLIENT_ID = client_secret

def _google_oauth_flow(state=None):
    """Create a request-scoped OAuth flow safe for concurrent workers."""
    return Flow.from_client_config(
        client_config=client_secret_dict,
        scopes=scopes,
        state=state,
        redirect_uri=url_for('authsblue.callback', _external=True),
    )


def _login_provider_enabled(config_key):
    """Honor the administrator-controlled login configuration."""
    from modules.users.users import get_login_config
    return bool(get_login_config().get(config_key, False))


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
    if not _login_provider_enabled('google_login_enabled'):
        flash('Google login is currently disabled')
        return redirect(url_for('authsblue.login'))
    # asking the flow class for the authorization (login) url
    oauth_flow = _google_oauth_flow()
    authorization_url, state = oauth_flow.authorization_url(
        prompt='select_account',
    )
    session.permanent = True
    session['state'] = state
    return redirect(authorization_url)

# Okta login route
@authsblue.route("/oktalogin")
def oktalogin():
    if not _login_provider_enabled('okta_login_enabled'):
        flash('Okta login is currently disabled')
        return redirect(url_for('authsblue.login'))
    # Fetch latest Okta secrets
    dynamic_okta_client_id = getsecrets("okta_client_id", project_id)
    dynamic_okta_issuer = getsecrets("okta_issuer", project_id)
    
    if not dynamic_okta_client_id or not dynamic_okta_issuer:
        flash("Okta authentication is not fully configured. Please contact an administrator.")
        return redirect(url_for("authsblue.login"))

    # Build Okta authorization URL
    nonce = secrets.token_urlsafe(32)
    params = {
        "client_id": dynamic_okta_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": url_for("authsblue.oktacallback", _external=True),
        "state": uuid.uuid4().hex,
        "nonce": nonce,
    }
    session["okta_state"] = params["state"]
    session["okta_nonce"] = nonce
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
    session.pop('okta_state', None)

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
    response = requests.post(token_url, data=data, auth=auth, timeout=10)
    response.raise_for_status()
    token_data = response.json()

    id_token_jwt = token_data.get("id_token")
    if not id_token_jwt:
        flash("Failed to login with Okta")
        return redirect(url_for("authsblue.login"))

    try:
        decoded_token = _verify_oidc_token(
            id_token_jwt,
            dynamic_okta_issuer,
            dynamic_okta_client_id,
            session.pop('okta_nonce', None),
        )
    except jwt.PyJWTError:
        logging.exception('Okta ID token verification failed')
        abort(403)

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
    user_data = _load_or_create_user(id_info)

    # Generate JWT token
    user_jwt_data = {
        'google_id': id_info['sub'],
        'name': user_data['name'],
        'photo': user_data.get('avatar', ''),
        'email': user_data['email'],
        'uuid': user_data.get('uuid'),
        'customer_id': user_data['customer_id'],
        'role': user_data['role'],
        'nro': user_data.get('nro'),
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
    if not _login_provider_enabled('odc_login_enabled'):
        flash('ODC login is currently disabled')
        return redirect(url_for('authsblue.login'))
    # Build ODC authorization URL
    nonce = secrets.token_urlsafe(32)
    params = {
        "client_id": odc_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": url_for("authsblue.odccallback", _external=True),
        "state": uuid.uuid4().hex,
        "nonce": nonce,
    }
    session["odc_state"] = params["state"]
    session["odc_nonce"] = nonce
    authorize_url = f"{odc_issuer.rstrip('/')}/v1/authorize"
    request_url = f"{authorize_url}?{urllib.parse.urlencode(params)}"
    return redirect(request_url)


@authsblue.route("/odccallback")
def odccallback():
    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("odc_state"):
        abort(403)
    session.pop('odc_state', None)

    token_url = f"{odc_issuer.rstrip('/')}/v1/token"
    auth = (odc_client_id, odc_client_secret)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": url_for("authsblue.odccallback", _external=True)
    }
    response = requests.post(token_url, data=data, auth=auth, timeout=10)
    response.raise_for_status()
    token_data = response.json()

    id_token_jwt = token_data.get("id_token")
    if not id_token_jwt:
        flash("Failed to login with ODC")
        return redirect(url_for("authsblue.login"))

    try:
        decoded_token = _verify_oidc_token(
            id_token_jwt,
            odc_issuer,
            odc_client_id,
            session.pop('odc_nonce', None),
        )
    except jwt.PyJWTError:
        logging.exception('ODC ID token verification failed')
        abort(403)

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

    user_data = _load_or_create_user(id_info)

    user_jwt_data = {
        'google_id': id_info['sub'],
        'name': user_data['name'],
        'photo': user_data.get('avatar', ''),
        'email': user_data['email'],
        'uuid': user_data.get('uuid'),
        'customer_id': user_data['customer_id'],
        'role': user_data['role'],
        'nro': user_data.get('nro'),
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
        'nro': user_data.get('nro'),
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
    expected_state = session.get("state")
    returned_state = request.args.get("state")
    if not expected_state or not returned_state or not secrets.compare_digest(expected_state, returned_state):
        logging.warning(
            "Google OAuth callback rejected: state cookie was missing or did not match"
        )
        session.clear()
        flash("Your login session expired or could not be verified. Please try signing in again.")
        return redirect(url_for('authsblue.login'))

    state = session.pop("state", None)
    oauth_flow = _google_oauth_flow(state=state)
    oauth_flow.fetch_token(authorization_response=request.url)

    credentials = oauth_flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    # the final page where the authorized users will end up
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    #
    # This code is to limit the login to a specific domain
    #
    email = id_info.get("email")
    domain = email.rsplit('@', 1)[-1].lower() if email and '@' in email else ''
    if domain != str(restrciteddomain).strip().lower():
        flash('You are not allowed to login to this site!')
        return redirect(url_for('frontpageblue.index'))

    # Check if the user exists in Firestore
    user_data = _load_or_create_user(id_info)

    # Generate user data for JWT token
    user_jwt_data = {
        'google_id': id_info.get("sub"),
        'name': id_info.get("name"),
        'photo': id_info.get("picture"),
        'email': id_info.get("email"),
        'uuid': user_data["uuid"],
        'customer_id': user_data["customer_id"],
        'role': user_data["role"],
        'nro': user_data.get('nro'),
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


def rate_limit(limit=RATE_LIMIT, window=RATE_WINDOW):
    def decorator(func):
        @wraps(func)  # preserves original function name
        def _rate_limiter(*args, **kwargs):  # unique inner name
            now = time.time()
            identity = request.headers.get('X-API-Key') or request.remote_addr or 'unknown'
            bucket = int(now // window)
            key = hashlib.sha256(
                f'{request.endpoint}:{identity}:{bucket}'.encode('utf-8')
            ).hexdigest()
            doc_ref = rate_limit_ref.document(key)
            transaction = db.transaction()

            @firestore.transactional
            def increment_rate_limit(txn):
                snapshot = doc_ref.get(transaction=txn)
                count = (snapshot.to_dict() or {}).get('count', 0) if snapshot.exists else 0
                if count >= limit:
                    return False
                txn.set(doc_ref, {
                    'count': count + 1,
                    'expires_at': datetime.utcnow() + timedelta(seconds=window * 2),
                })
                return True

            if not increment_rate_limit(transaction):
                return jsonify({"error": "Too many requests"}), 429
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
            decoded_data = decode_internal_jwt_token(jwt_token)
            if not decoded_data:
                return redirect(url_for('authsblue.logout'))
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

        user_snapshot = users_ref.document(user_id).get()
        if not user_snapshot.exists or (user_snapshot.to_dict() or {}).get('disabled', False):
            session.clear()
            abort(403)
        current_user = user_snapshot.to_dict() or {}
        decoded_data.update({
            'role': current_user.get('role', 'User'),
            'nro': current_user.get('nro'),
            'uuid': current_user.get('uuid'),
        })
        g.current_user = decoded_data

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
            decoded = getattr(g, 'current_user', None) or decode_internal_jwt_token(jwt_token)
            if not decoded:
                return redirect(url_for('authsblue.logout'))
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
    key_hash = hashlib.sha256(provided_api_key.encode('utf-8')).hexdigest()
    docs = apikeys_ref.where("api_key_hash", "==", key_hash).limit(1).get()
    # Temporary compatibility for keys created before hashing was introduced.
    legacy_key = False
    if not docs:
        docs = apikeys_ref.where("api_key", "==", provided_api_key).limit(1).get()
        legacy_key = bool(docs)
    if not docs:
        return False, "API key not found"

    key_data = docs[0].to_dict()

    if not key_data.get("active", False):
        return False, "API key inactive"

    # Transparently migrate old plaintext keys after a successful lookup.
    if legacy_key:
        docs[0].reference.update({
            'api_key_hash': key_hash,
            'api_key_prefix': provided_api_key[:6],
            'api_key': firestore.DELETE_FIELD,
        })

    g.api_key_owner = key_data.get('user_uuid') or 'API user'

    return True, None


def require_valid_api_key(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return '', 200

        provided_api_key = request.headers.get("X-API-Key")
        if not provided_api_key:
            return jsonify({
                "error": "Unauthorized access",
                "reason": "Missing API key. Provide it using the X-API-Key header",
            }), 403

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
    return decode_internal_jwt_token(token)


# Function to retrieve user data from JWT token
def get_user_data_from_token():
    if getattr(g, 'current_user', None):
        return g.current_user
    jwt_token = session.get('jwt_token')
    if jwt_token:
        user_data = decode_jwt_token(jwt_token)
        return user_data
    return None


# Create a cuctomer_id
def generate_customer_id(length=8):
    characters = string.ascii_letters + string.digits
    customer_id = ''.join(secrets.choice(characters) for _ in range(length))
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
        'role': 'User',
        'permissions': permissions if permissions else [],
        'groups': groups if groups else [],
        'disabled': False,
        'uuid': uuid_str
    }
    users_ref.document(id_info['sub']).set(user_data)

    return user_data
