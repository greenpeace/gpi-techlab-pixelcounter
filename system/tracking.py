from flask import request, session

DNT_TRACK = True  #False
IGNORE_IPS = set(['127.0.0.1'])


def is_tracking_allowed():
    if request.headers.get('DNT') == '1':
        return False
    if request.remote_addr in IGNORE_IPS:
        return False
    return True


def track_session():
    return session.get('track_session') is True
