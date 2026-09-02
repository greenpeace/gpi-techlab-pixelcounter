"""Object-level authorization helpers."""

from flask import abort

from system.jwt_utils import get_user_data_from_token


def can_manage_resource(resource):
    """Allow administrators, owners, assignees, or users in the same NRO."""
    user = get_user_data_from_token() or {}
    if user.get('role') == 'Administrator':
        return True

    identifiers = {value for value in (user.get('google_id'), user.get('uuid')) if value}
    if resource.get('uuid') in identifiers or resource.get('uid') in identifiers:
        return True

    if identifiers.intersection(set(resource.get('assigned_users') or [])):
        return True

    return (
        resource.get('type') == 'local'
        and bool(user.get('nro'))
        and resource.get('nro') == user.get('nro')
    )


def require_resource_access(snapshot):
    """Return document data or stop with the appropriate HTTP response."""
    if not snapshot.exists:
        abort(404)
    data = snapshot.to_dict() or {}
    if not can_manage_resource(data):
        abort(403)
    return data
