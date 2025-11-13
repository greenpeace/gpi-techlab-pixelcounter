from flask import (
    Blueprint,
    g,
    jsonify,
    session,
    request,
    url_for,
    redirect,
    render_template,
    flash
)

# for 2FA
import pyotp
import qrcode
import io
import base64
# Firestore
from google.cloud import firestore

# Fake News firestore collection
from system.firstoredb import users_ref
from system.firstoredb import login_config_ref
# from system.firstoredb import update_records_with_customer_id_and_uuid_in_batches
from modules.auth.auth import login_is_required, admin_required
from modules.auth.auth import get_user_data_from_token

# JWT
import jwt
usersblue = Blueprint('usersblue',
                      __name__,
                      template_folder='templates')


# API Route
@usersblue.route("/usersadd",
                 methods=['GET'],
                 endpoint='users_add')
@login_is_required
@admin_required
def users_add():
    return render_template('usersadd.html',
                           nonce=g.nonce)


@usersblue.route("/user-management",
                 methods=['GET', 'POST'],
                 endpoint='user-management')
@login_is_required
@admin_required
def usermanage():
    users = [doc.to_dict() for doc in users_ref.stream()]
    return render_template("users.html", users=users)


#
# API Route add a counter by ID - requires json file body with id and count
#
@usersblue.route("/userscreate",
                 methods=['POST'],
                 endpoint='users_create')
@login_is_required
@admin_required
def users_create():
    # Email
    from system.sendnotification import send_notification_email

    jwt_token = session.get('jwt_token')
    decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

    try:
        # Create the user
        data = {
            u'url': request.form.get('url'),
            u'given_name': request.form.get('given_name'),
            u'last_name': request.form.get('last_name'),
            u'email': request.form.get('email'),
            u'phone': request.form.get('phone'),
            u'designation': request.form.get('designation'),
            u'role': request.form.get('role'),
            u'disabled': False,
            u'user': decoded_data.get('name'),
            u'uuid': decoded_data.get('uuid'),
            u'customer_id': decoded_data.get('customer_id')
        }

        users_ref.document().set(data)
        # Send Email
        credentials = session['credentials']
        user_email = 'tzetter@socialclimate.tech'
        subject = "Account Created Successfully"
        body = "Dear User,\n\nYour account has been successfully created. \
            Thank you for joining our platform.\n\nBest regards,\nThe App Team"
        send_notification_email(user_email, subject, body, credentials)
        flash('Data Succesfully Submitted')
        return redirect(url_for('usersblue.userslist'))
    except Exception as e:
        flash('An Error Occvured')
        return f"An Error Occured: {e}"

#
# the enable 2fa
#


@usersblue.route('/enable-2fa',
                 endpoint='enable_2fa')
@login_is_required
@admin_required
def enable_2fa():
    user_data = get_user_data_from_token()
    user_doc = users_ref.document(user_data['google_id']).get().to_dict()

    if not user_doc.get('totp_enabled', False):
        totp_secret = pyotp.random_base32()
        users_ref.document(user_data['google_id']).update({'totp_secret': totp_secret})

        totp = pyotp.TOTP(totp_secret)
        totp_uri = totp.provisioning_uri(user_data['email'], issuer_name="YourAppName")

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert image to base64 for displaying in HTML
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return render_template('enable_2fa.html', qr_code=img_str, secret=totp_secret)
    else:
        flash('2FA is already enabled for your account.', 'info')
        return redirect(url_for('usersblue.user_profile'))

#
# the enable 2fa
#


@usersblue.route('/verify-enable-2fa',
                 methods=['POST'],
                 endpoint='verify_enable_2fa')
@login_is_required
@admin_required
def verify_enable_2fa():
    user_data = get_user_data_from_token()
    user_doc_ref = users_ref.document(user_data['google_id'])
    user_doc = user_doc_ref.get().to_dict()

    totp_secret = user_doc['totp_secret']
    totp = pyotp.TOTP(totp_secret)

    user_token = request.form.get('token')

    if totp.verify(user_token):
        user_doc_ref.update({'totp_enabled': True})
        flash('2FA has been successfully enabled for your account.', 'success')
        return redirect(url_for('dashboardblue.main'))
    else:
        flash('Invalid token. Please try again.', 'error')
        return redirect(url_for('usersblue.enable_2fa'))

#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@usersblue.route("/users",
                 methods=['GET'],
                 endpoint='userslist')
@login_is_required
@admin_required
def userslist():

    jwt_token = session.get('jwt_token')
    decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

    # Check if ID was passed to URL query
    id = request.args.get('id')
    if id:
        users = users_ref.document(id).get()
        return jsonify(u'{}'.format(users.to_dict()['count'])), 200

    # Get the UUID, organization ID, and role from the session
    uuid = decoded_data.get("uuid")
    customer_id = decoded_data.get("customer_id")
    role = decoded_data.get("role")

    # Call the function to update the records
    # update_records_with_customer_id_and_uuid_in_batches(users_ref, customer_id, uuid)

    # Check if the UUID, organization ID, and role exist in the session
    if uuid is None or customer_id is None or role is None:
        # Handle the case when UUID, organization ID, or role is missing from the session
        # build in error handling messages and than redirect
        return redirect(url_for('dashboardblue.main'))
    try:
        all_users = []
        query = None

        if role == "Administrator":
            # Administrator role can see all users
            query = users_ref
        else:
            # Regular users see only their own records
            query = users_ref.where('customer_id', '==', customer_id).where('uuid', '==', uuid)

        data = query.stream()

        for doc in data:
            don = doc.to_dict()
            don["docid"] = doc.id
            all_users.append(don)

        return render_template('users.html',
                               output=all_users,
                               nonce=g.nonce)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@usersblue.route("/usersedit",
                 methods=['GET'],
                 endpoint='userss_edit')
@login_is_required
@admin_required
def users_edit():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        users = users_ref.document(id).get()
        users = users.to_dict()
        users["id"] = id
        return render_template('usersedit.html',
                               users=users,
                               nonce=g.nonce)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@usersblue.route("/usersdelete",
                 methods=['GET', 'DELETE'],
                 endpoint='users_delete')
@login_is_required
@admin_required
def users_delete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        users_ref.document(id).delete()
        return redirect(url_for('usersblue.userslist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@usersblue.route("/usersupdate",
                 methods=['POST', 'PUT'],
                 endpoint='users_update')
@login_is_required
@admin_required
def users_update():

    try:
        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])
        # Get the id
        id = request.form.get('id')
        # Create the user
        data = {
            u'url': request.form.get('url'),
            u'given_name': request.form.get('given_name'),
            u'last_name': request.form.get('last_name'),
            u'email': request.form.get('email'),
            u'phone': request.form.get('phone'),
            u'designation': request.form.get('designation'),
            u'role': request.form.get('role'),
            u'disabled': False,
            u'user': decoded_data.get('name'),
            u'uuid': decoded_data.get('uuid'),
            u'customer_id': decoded_data.get('customer_id')
        }

        users_ref.document(id).update(data)
        return redirect(url_for('usersblue.userslist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@usersblue.route("/usersupdateform",
                 methods=['POST', 'PUT'],
                 endpoint='users_updateform')
@login_is_required
@admin_required
def users_updateform():
    try:
        id = request.form['id']
        users_ref.document(id).update(request.form)
        return redirect(url_for('usersblue.userslist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@usersblue.route("/usersactive",
                 methods=['GET', 'DELETE'],
                 endpoint='users_active')
@login_is_required
@admin_required
def users_active():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        users = users_ref.document(id).get()
        usersactive = users.to_dict()

        # Update flag that translation done
        if usersactive['disabled'] is True:
            data = {
                u'disabled': False,
            }
        else:
            data = {
                u'disabled': True,
            }
        users_ref.document(id).update(data)
        return redirect(url_for('usersblue.userslist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# Config User Login
#


@usersblue.route('/password/edit', methods=['POST'])
@login_is_required
@admin_required
def edit_password():
    data = request.get_json()

    # Validate input
    if not all(key in data for key in ['currentPassword', 'newPassword', 'confirmPassword']):
        return jsonify({'success': False, 'message': 'Invalid input'}), 400

    if data['newPassword'] != data['confirmPassword']:
        return jsonify({'success': False, 'message': 'New passwords do not match'}), 400

    # Add your password update logic here
    # Verify current password, update to new password, etc.

    return jsonify({'success': True, 'message': 'Password updated successfully'})


@usersblue.route('/admin/admin_login-config',
                 methods=['GET', 'POST'],
                 endpoint='admin_login_config')
@login_is_required
@admin_required
def admin_login_config():
    if request.method == 'POST':
        new_config = {
            'email_login_enabled': 'email_login' in request.form,
            'okta_login_enabled': 'okta_login' in request.form,
            'google_login_enabled': 'google_login' in request.form,
            'apple_login_enabled': 'apple_login' in request.form
        }
        login_config_ref.document('config').update(new_config)
        flash('Login configuration updated successfully')
        return redirect(url_for('usersblue.admin_login_config'))

    config = get_login_config()
    return render_template('loginconfig.html', config=config)


def get_login_config():
    try:
        # Fetch the document using the login_config_ref
        doc = login_config_ref.document('config').get()

        # Check if the result is a DocumentSnapshot and if the document exists
        if not isinstance(doc, firestore.DocumentSnapshot):
            raise TypeError("Expected DocumentSnapshot, got something else.")

        if doc.exists:
            return doc.to_dict()
        else:
            # Default configuration
            default_config = {
                'email_login_enabled': True,
                'okta_login_enabled': True,
                'google_login_enabled': True,
                'apple_login_enabled': True
            }
            # Save the default configuration to the document
            login_config_ref.document('config').set(default_config)
            return default_config

    except Exception as e:
        print(f"An error occurred: {e}")
        # Optional: log the error for debugging purposes
        return None
