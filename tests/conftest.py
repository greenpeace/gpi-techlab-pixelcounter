import json
import os


# Authentication imports normally resolve these values from Secret Manager.
# Unit tests provide inert values so collection never depends on the network.
os.environ.setdefault('PIXELCOUNTER_SECRET_CLIENT_SECRET_KEY', 'test-client-secret')
os.environ.setdefault('PIXELCOUNTER_SECRET_APP_SECRET_KEY', 'test-app-secret')
os.environ.setdefault('PIXELCOUNTER_SECRET_RESTRCITEDDOMAIN', 'example.org')
os.environ.setdefault('PIXELCOUNTER_SECRET_OKTA_CLIENT_ID', 'test-okta-client')
os.environ.setdefault('PIXELCOUNTER_SECRET_OKTA_CLIENT_SECRET', 'test-okta-secret')
os.environ.setdefault('PIXELCOUNTER_SECRET_OKTA_ISSUER', 'https://example.okta.com/oauth2/default')
os.environ.setdefault('PIXELCOUNTER_SECRET_ODC_CLIENT_ID', 'test-odc-client')
os.environ.setdefault('PIXELCOUNTER_SECRET_ODC_CLIENT_SECRET', 'test-odc-secret')
os.environ.setdefault('PIXELCOUNTER_SECRET_ODC_ISSUER', 'https://example.org/oauth2/default')
os.environ.setdefault(
    'PIXELCOUNTER_SECRET_CLIENT_SECRET_FILE',
    json.dumps({
        'web': {
            'client_id': 'test-google-client',
            'client_secret': 'test-google-secret',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
        }
    }),
)
