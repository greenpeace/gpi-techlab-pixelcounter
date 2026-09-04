try:
    from firebase_admin import credentials, firestore
    import firebase_admin
except Exception as e:
    # Fallback dummy classes for environments without firebase_admin
    class _Dummy:
        def __getattr__(self, name):
            raise NotImplementedError("Firebase functionality is unavailable in this environment.")
    credentials = _Dummy()
    firestore = _Dummy()
    firebase_admin = _Dummy()
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
    # apikeys collection
    apikeys_ref = db.collection(u'apikeys')
    # login config
    login_config_ref = db.collection(u'login_config')
    # Data colelction to store all documents that should be used for indexing for vector
    blogpost_ref = db.collection(u'blog')
    # System activity logs collection
    activity_ref = db.collection(u'system_activity')
    rate_limit_ref = db.collection(u'api_rate_limits')
    documentation_ref = db.collection(u'documentation')
    page_permissions_ref = db.collection(u'page_permissions')

    # nro collection
    nro_ref = db.collection(u'nro')
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
    qrcode_ref = db.collection(u'qrcode-test')
    # shorten url
    molnurl_ref = db.collection(u'moln-url-test')
    # shorten url
    users_ref = db.collection(u'users-test')
    # apikeys collection
    apikeys_ref = db.collection(u'apikeys-test')
    # Data colelction to store all documents that should be used for indexing for vector
    blogpost_ref = db.collection(u'blog-test')

    # CRM to track any request from contactform
    login_config_ref = db.collection(u'login_config-test')

    # nro collection
    nro_ref = db.collection(u'nro-test')
    # Activity logs collection for test environment
    activity_ref = db.collection(u'system_activity-test')
    rate_limit_ref = db.collection(u'api_rate_limits-test')
    documentation_ref = db.collection(u'documentation-test')
    page_permissions_ref = db.collection(u'page_permissions-test')
