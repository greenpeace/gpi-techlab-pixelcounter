import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app, session


def generate_jwt_token(user_data):
    now = datetime.now(timezone.utc)
    claims = dict(user_data)
    claims.update({
        'iat': now,
        'exp': now + timedelta(minutes=30),
        'iss': 'pixelcounter',
        'aud': 'pixelcounter-web',
    })
    return jwt.encode(claims, current_app.config['JWT_SECRET'], algorithm='HS256')


def decode_jwt_token(token):
    try:
        decoded_data = jwt.decode(
            token,
            current_app.config['JWT_SECRET'],
            algorithms=['HS256'],
            audience='pixelcounter-web',
            issuer='pixelcounter',
            options={'require': ['exp', 'iat', 'iss', 'aud']},
        )
        return decoded_data
    except jwt.ExpiredSignatureError:
        # Handle expired token
        return None
    except jwt.InvalidTokenError:
        # Handle invalid token
        return None


# Function to retrieve user data from JWT token


def get_user_data_from_token():
    jwt_token = session.get('jwt_token')
    if jwt_token:
        user_data = decode_jwt_token(jwt_token)
        return user_data
    return None
