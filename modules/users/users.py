
from flask import Blueprint, g, request, session, jsonify, url_for, redirect, render_template, flash
from flask_cors import CORS,cross_origin
# to get meta details from an url
import requests
from bs4 import BeautifulSoup
import base64
# Date and stuff
import time
# Get Logging
import logging

# Get BigQuery
import system.bigquery

# Install Google Libraries
from google.cloud.firestore import Increment

# Journalist firestore collection
from system.firstoredb import user_ref
from system.date import datenow

user_billing = Blueprint('user_billing', __name__, template_folder='templates')

from modules.auth.auth import login_is_required
# Import project id
from system.setenv import project_id
from system.getsecret import getsecrets


@user_billing.route('/list-users', methods=['GET'], endpoint='list_users') 
@login_is_required
def list_users(): 

    #get all users from firestore 
    users = user_ref.get()

    #create an empty list to store user data 
    user_data = []

    #iterate over the users and append their data to the list 
    for user in users: 
        user_data.append(user.to_dict())

    #return the list of user data 
    return user_data

 # Create a route for creating new users 
@user_billing.route('/create-user', methods=['POST'], endpoint='create_users') 
@login_is_required
def create_user(): 
    data = request.get_json() 

    # Add a new document to the users collection 
    doc_ref = user_ref.document(data['username']) 

    # Set the data for the new user document 
    doc_ref.set({ 
        u'username': data['username'], 
        u'password': data['password'] 
    })

    return 'User created successfully!'

 # Create a route for updating user billing information  
@user_billing.route('/update-billing', methods=['POST'],  endpoint='update_billing') 
@login_is_required 
def update_billing():  														   
    data = request.get_json()
    doc_ref = user_ref.document(data['username'])  

    doc_ref.update({   u'billing': {     u'street': data['street'],     u'city': data['city']     }   }) 

    return('Billing information updated successfully!')