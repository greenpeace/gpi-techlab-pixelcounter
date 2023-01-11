from flask import current_app as app
from firebase_admin import credentials, firestore
import firebase_admin
from system.setenv import project_id

# initialize firebase sdk
CREDENTIALS = credentials.ApplicationDefault()
firebase_admin.initialize_app(CREDENTIALS, {
    'projectId': project_id,
})

# Initialize Firestore DB
db = firestore.client()

# Counters firestore collection
counter_ref = db.collection(u'counters')
# Allowed origion collection
allowedorigion_ref = db.collection(u'allowedorigion')
# Allowed origion collection
emailhash_ref = db.collection(u'amialhash')
# qrcode
qrcode_ref = db.collection(u'qrcode')
# shorten url
molnurl_ref = db.collection(u'moln-url')
