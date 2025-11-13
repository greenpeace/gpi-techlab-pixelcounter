# Local imports
import datetime
import pytz


def datenow():
    # return datetime.now().timestamp()
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
