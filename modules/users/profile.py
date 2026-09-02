from flask import (
    Blueprint,
    g,
    flash,
    request,
    redirect,
    render_template,
    url_for
)

# Fake News firestore collection
from system.firstoredb import users_ref
from modules.auth.auth import login_is_required
from modules.auth.auth import get_user_data_from_token
from system.activity import log_activity
import logging

profileblue = Blueprint('profileblue',
                        __name__,
                        template_folder='templates')

# Profile
#
# API Route


@profileblue.route("/user_profile",
                   methods=['GET', 'POST'],
                   endpoint='user_profile')
@login_is_required
def user_profile():
    try:
        # Check if ID was passed to URL query
        nonce = g.nonce
        user_data = get_user_data_from_token()
        user_doc = users_ref.document(user_data['google_id']).get().to_dict()

        if request.method == 'POST':
            given_name = request.form.get('given_name', '').strip()
            family_name = request.form.get('family_name', '').strip()
            if not given_name or not family_name:
                flash('First name and last name are required.', 'error')
                return redirect(url_for('profileblue.user_profile'))

            # Update user profile
            updates = {
                'given_name': given_name,
                'family_name': family_name,
                'name': f'{given_name} {family_name}',
                'user': f'{given_name} {family_name}',
                'phone': request.form.get('phone', '').strip()
            }
            users_ref.document(user_data['google_id']).update(updates)
            log_activity('updated', 'user profile', user_data['google_id'], updates['name'])
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('profileblue.user_profile'))

        return render_template('profile.html', user=user_doc,
                               nonce=nonce)
    except Exception:
        logging.exception('Unable to load or update user profile')
        return render_template('500.html'), 500
