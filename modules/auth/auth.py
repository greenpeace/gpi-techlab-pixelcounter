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
    render_template
)
import requests
import json
import random
import string
import uuid
import jwt
import logging
from datetime import datetime, timedelta

# Get Google Login with oauth
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from pip._vendor import cachecontrol

from system.firstoredb import users_ref
from system.jwt_utils import generate_jwt_token
from system.getsecret import getsecrets
# Import project id
from system.setenv import project_id

authsblue = Blueprint('authsblue', __name__)

# Get the secret for Service Account
# Get the secret for Service Account
client_secret = getsecrets("client_secret_key", project_id)
app_secret_key = getsecrets("app_secret_key", project_id)
restrciteddomain = getsecrets("restrciteddomain", project_id)

# Retrieve the secret values
secret_value = getsecrets("client_secret_file", project_id)
client_secret_dict = json.loads(secret_value)

scopes = ["https://www.googleapis.com/auth/userinfo.profile",
          "https://www.googleapis.com/auth/userinfo.email",
          "openid"
]

is_production = os.getenv('IS_PRODUCTION', 'false').lower() == 'true'

# if not is_production:
#    # this is to set our environment to https because OAuth 2.0
#    # only supports https environments
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# enter your client id you got from Google console

GOOGLE_CLIENT_ID = client_secret

redirect_uri = (
    "https://counter.greenpeace.org/callbackk" if is_production else
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


@authsblue.route("/loginseq")  #the page where the user can login
def loginseq():
    #asking the flow class for the authorization (login) url
    authorization_url, state = flow.authorization_url()
    session.permanent = True
    session['state'] = state
    return redirect(authorization_url)

# this is the page that will handle the callback process meaning 
# process after the authorization


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

    # Store user data in the session
    session['name'] = id_info.get("name")
    session['photo'] = id_info.get("picture")
    session['uuid'] = user_data["uuid"]
    session['customer_id'] = user_data["customer_id"]
    session['role'] = user_data["role"]
    session['language'] = id_info.get("locale")

    return redirect(url_for('dashboardblue.main'))

# a function to check if the user is authorized or not


def login_is_required(function):
    def wrapper(*args, **kwargs):
        jwt_token = session.get('jwt_token')

        if not jwt_token:
            # Redirect to logout if JWT token is not present
            return redirect(url_for('authsblue.logout'))

        try:
            decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])
            user_id = decoded_data.get('google_id')  # Adjust to match the key used in your JWT token
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
        return function(*args, **kwargs)

    return wrapper


def logout_inactive_users():
    last_activity_time_str = session.get('last_activity_time')
    if last_activity_time_str:
        last_activity_time = datetime.strptime(last_activity_time_str, "%Y-%m-%d %H:%M:%S")
        time_since_activity = datetime.now() - last_activity_time
        if time_since_activity > timedelta(minutes=30):  # Adjust to your desired inactivity timeout
            session.clear()
            return redirect(url_for('authsblue.logout'))


@authsblue.before_request
def before_request():
    logout_inactive_users()


@authsblue.after_request
def after_request(response):
    session['last_activity_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return response

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
        'permissions': permissions if permissions else [],
        'groups': groups if groups else [],
        'disabled': False,
        'uuid': uuid_str
    }
    users_ref.document(id_info['sub']).set(user_data)

    return user_data
