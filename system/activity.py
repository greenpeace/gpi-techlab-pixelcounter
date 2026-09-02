"""Shared system activity logging for dashboard-visible changes."""

from datetime import datetime, timezone
import logging

from flask import session

from system.firstoredb import activity_ref
from system.jwt_utils import decode_jwt_token


def _current_user(fallback="system"):
    """Return the best available identity for the current request."""
    if session.get("email"):
        return session["email"]

    token = session.get("jwt_token")
    if token:
        try:
            claims = decode_jwt_token(token)
            if not claims:
                return fallback or "system"
            return (
                claims.get("email")
                or claims.get("name")
                or claims.get("google_id")
                or fallback
            )
        except Exception:
            logging.debug('Unable to resolve activity user from the session token')

    return fallback or "system"


def log_activity(action, resource_type, resource_id, resource_name=None, user=None):
    """Write a configuration change to the environment's activity collection."""
    actor = user or _current_user()
    label = resource_name or resource_id
    timestamp = datetime.now(timezone.utc)
    message = f"{actor} {action} {resource_type} '{label}'."

    activity = {
        "action": action,
        "message": message,
        "resource_id": resource_id,
        "resource_name": resource_name or "",
        "resource_type": resource_type,
        "timestamp": timestamp,
        "user": actor,
    }

    try:
        activity_ref.add(activity)
    except Exception:
        # An audit outage must not turn an already-completed user change into
        # an apparent failure, but it must remain visible in application logs.
        logging.exception("Unable to write system activity: %s", activity)
