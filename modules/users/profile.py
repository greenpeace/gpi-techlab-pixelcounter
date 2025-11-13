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
            # Update user profile
            updates = {
                'given_name': request.form.get('given_name'),
                'last_name': request.form.get('last_name'),
                'phone': request.form.get('phone')
            }
            users_ref.document(user_data['google_id']).update(updates)
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('profileblue.user_profile'))

        return render_template('profile.html', user=user_doc,
                               nonce=nonce)
    except Exception as e:
        return f"An Error Occured: {e}"
