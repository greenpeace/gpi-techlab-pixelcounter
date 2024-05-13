import jwt
from flask import session


def generate_jwt_token(user_data):
    jwt_token = jwt.encode(user_data, 'secret_key', algorithm='HS256')
    return jwt_token


def decode_jwt_token(token):
    try:
        decoded_data = jwt.decode(token, 'secret_key', algorithms=['HS256'])
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
