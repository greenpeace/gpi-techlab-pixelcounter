# Get the Flask Files Required
import os
from flask import Blueprint, g, session, request, url_for, redirect, render_template, abort, flash
import pathlib
import requests
# Get Google Login with oauth
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from pip._vendor import cachecontrol
import random
import string
import uuid
from datetime import datetime, timedelta

from system.firstoredb import users_ref

from system.getsecret import getsecrets
# Import project id
from system.setenv import project_id

authsblue = Blueprint('authsblue', __name__)

# Get the secret for Service Account
client_secret = getsecrets("client-secret-key",project_id)
app_secret_key_newsdesk = getsecrets("app_secret_key",project_id)
restrciteddomain = getsecrets("restrciteddomain",project_id)

#this is to set our environment to https because OAuth 2.0 only supports https environments
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
#enter your client id you got from Google console
GOOGLE_CLIENT_ID = client_secret
#set the path to where the .json file you got Google console is
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")
#Flow is OAuth 2.0 a class that stores all the information on how we want to authorize our users
flow = Flow.from_client_secrets_file( 
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", 
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
            ],
    #and the redirect URI is the point where the user will end up after the authorization
    #redirect_uri="http://127.0.0.1:8080/callback"
    redirect_uri="https://counter.greenpeace.org/callback"
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

#this is the page that will handle the callback process meaning process after the authorization
@authsblue.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if session.get("state") != request.args.get("state"):
        print("Callback route not reached!")
        abort(500)  # State does not match!

    # Remove the state from the session
    session.pop("state", None)

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)
    
    #the final page where the authorized users will end up
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
           
    # Store user data in the session
    session['credentials'] = credentials.token
    session['google_id'] = id_info.get("sub")
    session['name'] = id_info.get("name")
    session['photo'] = id_info.get("picture")
    session['email'] = id_info.get("email")
    session['uuid'] = user_data["uuid"]
    session['customer_id'] = user_data["customer_id"]
    session['role'] = user_data["role"]
    session['language'] = id_info.get("locale")   
    return redirect(url_for('dashboardblue.main'))

#a function to check if the user is authorized or not
def login_is_required(function):
    def wrapper(*args, **kwargs):
        # Check if the "google_id" is present in the session
        if "google_id" not in session:
            # Clear the session before redirecting to logout
            session.clear()
            return redirect(url_for('authsblue.logout'))

        # Check if the session has an entry for last_activity_time
        if 'last_activity_time' in session:
            # Retrieve last_activity_time as a datetime object
            last_activity_time_str = session['last_activity_time']
            last_activity_time = datetime.strptime(last_activity_time_str, "%Y-%m-%d %H:%M:%S")

            time_since_activity = datetime.now() - last_activity_time

            # If there is more than 5 minutes of inactivity, clear the session and redirect to logout
            if time_since_activity > timedelta(minutes=5):
                session.clear()
                return redirect(url_for('authsblue.logout'))

        # Update the last_activity_time in the session on every request
        session['last_activity_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Call the original function
        return function(*args, **kwargs)
    # return
    return wrapper

# Create a cuctomer_id
def generate_customer_id(length=8):
    characters = string.ascii_letters + string.digits
    customer_id = ''.join(random.choice(characters) for _ in range(length))
    return customer_id

# create a user
def create_new_user(id_info):
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
        'role': 'ADMINISTRATOR',
        'permissions': '',
        'designation': 'Administrator',
        'disabled': False,
        'phone': '',
        'uuid': uuid_str
    }
    users_ref.document(id_info['sub']).set(user_data)

    return user_data
