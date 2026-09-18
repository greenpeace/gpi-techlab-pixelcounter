"""Responses shared by modal forms and their non-JavaScript fallback pages."""

from flask import flash, jsonify, redirect, request, url_for
from werkzeug.exceptions import HTTPException


def is_modal_request():
    return request.headers.get('X-Modal-Form') == '1'


def form_success(endpoint, message='Saved successfully.', **values):
    if is_modal_request():
        return jsonify(success=True, message=message)
    flash(message, 'success')
    return redirect(url_for(endpoint, **values))


def form_error(message, endpoint=None, status=400, **values):
    if isinstance(message, HTTPException):
        status = message.code
        message = message.description
    message = str(message)
    if is_modal_request():
        return jsonify(success=False, error=message), status
    if endpoint:
        flash(message, 'error')
        return redirect(url_for(endpoint, **values))
    return message, status
