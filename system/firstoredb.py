from flask import current_app as app
from firebase_admin import credentials, firestore
import firebase_admin
import os
from system.setenv import project_id

# initialize firebase sdk
CREDENTIALS = credentials.ApplicationDefault()
firebase_admin.initialize_app(CREDENTIALS, {
    'projectId': project_id,
})

# Initialize Firestore DB
db = firestore.client()

is_production_db = os.getenv('IS_PRODUCTION_DB', 'false').lower() == 'true'

if is_production_db:
    # Counters firestore collection
    counter_ref = db.collection(u'counters')
    # Allowed origion collection
    allowedorigion_ref = db.collection(u'allowedorigion')
    # Allowed certain allowed urls shoudl be dissalowed 
    disallowedorigion_ref = db.collection(u'disallowedorigion')
    # Allowed origion collection
    emailhash_ref = db.collection(u'amialhash')
    # qrcode
    qrcode_ref = db.collection(u'qrcode')
    # shorten url
    molnurl_ref = db.collection(u'moln-url')
    # shorten url
    users_ref = db.collection(u'users')
    # Data colelction to store all documents that should be used for indexing for vector
    blogpost_ref = db.collection(u'blog')

    # CRM to track any request from contactform
    crm_ref = db.collection("legalcrm")
else:
    # Counters firestore collection
    counter_ref = db.collection(u'counters-test')
    # Allowed origion collection
    allowedorigion_ref = db.collection(u'allowedorigion-test')
    # Allowed certain allowed urls shoudl be dissalowed 
    disallowedorigion_ref = db.collection(u'disallowedorigion-test')
    # Allowed origion collection
    emailhash_ref = db.collection(u'amialhash-test')
    # qrcode
    qrcode_ref = db.collection(u'qrcode-tet')
    # shorten url
    molnurl_ref = db.collection(u'moln-url-test')
    # shorten url
    users_ref = db.collection(u'users-test')
    # Data colelction to store all documents that should be used for indexing for vector
    blogpost_ref = db.collection(u'blog-test')

    # CRM to track any request from contactform
    crm_ref = db.collection("legalcrm-test")
