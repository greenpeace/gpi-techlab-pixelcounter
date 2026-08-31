# Local imports
from datetime import datetime, timezone

def datenow():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')