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
import logging
import hashlib
import secrets

# Firestore
from google.cloud import firestore

# Fake News firestore collection
from system.firstoredb import users_ref, counter_ref
from system.firstoredb import login_config_ref, nro_ref, page_permissions_ref
# from system.firstoredb import update_records_with_customer_id_and_uuid_in_batches
from modules.auth.auth import login_is_required, admin_required, generate_customer_id
from modules.auth.auth import get_user_data_from_token
from system.jwt_utils import decode_jwt_token
from system.activity import log_activity

from system.setenv import project_id

import uuid

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
    decoded_data = decode_jwt_token(jwt_token)

    try:
        # Create the user
        new_user_uuid = str(uuid.uuid4())
        display_name = f"{request.form.get('given_name', '')} {request.form.get('last_name', '')}".strip()
        data = {
            u'url': request.form.get('url'),
            u'given_name': request.form.get('given_name'),
            u'family_name': request.form.get('last_name'),
            u'email': request.form.get('email'),
            u'phone': request.form.get('phone'),
            u'designation': request.form.get('designation'),
            u'role': request.form.get('role') if request.form.get('role') in {'User', 'Administrator'} else 'User',
            u'disabled': False,
            u'name': display_name,
            u'user': display_name,
            u'uuid': new_user_uuid,
            u'customer_id': generate_customer_id()
        }

        users_ref.document().set(data)
        # Send Email
        credentials = session.get('credentials')
        user_email = data['email']
        subject = "Account Created Successfully"
        body = "Dear User,\n\nYour account has been successfully created. \
            Thank you for joining our platform.\n\nBest regards,\nThe App Team"
        if credentials:
            try:
                send_notification_email(user_email, subject, body, credentials)
            except Exception:
                logging.exception('User created, but the notification email failed')
        flash('Data Succesfully Submitted')
        return redirect(url_for('usersblue.userslist'))
    except Exception:
        logging.exception('Unable to create user')
        flash('An error occurred while creating the user')
        return redirect(url_for('usersblue.userslist'))

#
# the enable 2fa
#


@usersblue.route('/enable-2fa',
                 endpoint='enable_2fa')
@login_is_required
def enable_2fa():
    user_data = get_user_data_from_token()
    user_doc = users_ref.document(user_data['google_id']).get().to_dict() or {}

    if user_doc.get('totp_enabled', False):
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('profileblue.user_profile'))

    # Keep unverified setup material in the signed session. Nothing is enabled in
    # Firestore until the user proves that their authenticator is configured.
    totp_secret = session.get('pending_totp_secret') or pyotp.random_base32()
    recovery_codes = session.get('pending_totp_recovery_codes')
    if not recovery_codes:
        recovery_codes = [
            f'{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}'
            for _ in range(10)
        ]
    session['pending_totp_secret'] = totp_secret
    session['pending_totp_recovery_codes'] = recovery_codes

    totp_uri = pyotp.TOTP(totp_secret).provisioning_uri(
        user_data['email'], issuer_name='Greenpeace Counter App'
    )
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buffered = io.BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return render_template(
        'enable_2fa.html', qr_code=img_str, secret=totp_secret,
        recovery_codes=recovery_codes, account_email=user_data['email']
    )

#
# the enable 2fa
#


@usersblue.route('/verify-enable-2fa',
                 methods=['POST'],
                 endpoint='verify_enable_2fa')
@login_is_required
def verify_enable_2fa():
    user_data = get_user_data_from_token()
    user_doc_ref = users_ref.document(user_data['google_id'])
    totp_secret = session.get('pending_totp_secret')
    recovery_codes = session.get('pending_totp_recovery_codes') or []
    user_token = (request.form.get('token') or '').replace(' ', '')

    if not totp_secret:
        flash('Your 2FA setup session expired. Please start again.', 'error')
        return redirect(url_for('usersblue.enable_2fa'))
    if not pyotp.TOTP(totp_secret).verify(user_token, valid_window=1):
        flash('The verification code is invalid. Please try again.', 'error')
        return redirect(url_for('usersblue.enable_2fa'))

    recovery_hashes = [
        hashlib.sha256(code.replace('-', '').encode('utf-8')).hexdigest()
        for code in recovery_codes
    ]
    user_doc_ref.update({
        'totp_enabled': True,
        'totp_secret': totp_secret,
        'totp_recovery_code_hashes': recovery_hashes,
        'totp_enabled_at': firestore.SERVER_TIMESTAMP,
    })
    session.pop('pending_totp_secret', None)
    session.pop('pending_totp_recovery_codes', None)
    log_activity('enabled', 'two-factor authentication', user_data['google_id'])
    return render_template(
        'enable_2fa.html', enabled=True, recovery_codes=recovery_codes,
        account_email=user_data['email']
    )


@usersblue.route('/disable-2fa', methods=['POST'], endpoint='disable_2fa')
@login_is_required
def disable_2fa():
    user_data = get_user_data_from_token()
    user_doc_ref = users_ref.document(user_data['google_id'])
    user_doc = user_doc_ref.get().to_dict() or {}
    supplied_code = (request.form.get('token') or '').replace(' ', '').replace('-', '')
    secret = user_doc.get('totp_secret')
    recovery_hashes = user_doc.get('totp_recovery_code_hashes') or []
    recovery_hash = hashlib.sha256(supplied_code.upper().encode('utf-8')).hexdigest()
    valid_totp = bool(secret and pyotp.TOTP(secret).verify(supplied_code, valid_window=1))
    valid_recovery = recovery_hash in recovery_hashes

    if not supplied_code or not (valid_totp or valid_recovery):
        flash('Enter a valid authenticator or recovery code to disable 2FA.', 'error')
        return redirect(url_for('profileblue.user_profile'))

    user_doc_ref.update({
        'totp_enabled': False,
        'totp_secret': firestore.DELETE_FIELD,
        'totp_recovery_code_hashes': firestore.DELETE_FIELD,
        'totp_enabled_at': firestore.DELETE_FIELD,
    })
    log_activity('disabled', 'two-factor authentication', user_data['google_id'])
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('profileblue.user_profile'))

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
    decoded_data = decode_jwt_token(jwt_token)

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
        
        # Fetch all counters for the dropdown
        counters_stream = counter_ref.stream()
        counters = []
        user_uuid = users.get('uuid')
        
        for doc in counters_stream:
            c_data = doc.to_dict()
            # Determine if this counter is currently assigned to this user
            is_assigned = c_data.get('uuid') == user_uuid
            
            
            counters.append({
                "id": doc.id,
                "name": c_data.get("name", doc.id),
                "is_assigned": is_assigned
            })
            
        # Fetch all API Keys
        from system.firstoredb import apikeys_ref  
        apikeys_stream = apikeys_ref.stream()
        apikeys = []
        for doc in apikeys_stream:
            k_data = doc.to_dict()
            is_assigned_key = k_data.get('user_uuid') == user_uuid
            
            # Simple name: Key ID + snippet
            k_id = doc.id
            key_val = k_data.get('api_key', '')
            key_prefix = k_data.get('key_prefix') or k_data.get('api_key_prefix')
            mask = f"{key_prefix}..." if key_prefix else f"{key_val[:6]}...{key_val[-4:]}"
            
            apikeys.append({
                "id": k_id,
                "mask": mask,
                "is_assigned": is_assigned_key,
                "created_at": k_data.get('created_at')
            })
            
        # Fetch NROs
        nro_stream = nro_ref.stream()
        nros = []
        for doc in nro_stream:
            d = doc.to_dict()
            if d.get("active", True):
                nros.append(d.get("name"))
        nros.sort()
            
        return render_template('usersedit.html',
                               users=users,
                               counters=counters,
                               apikeys=apikeys,
                               nros=nros,
                               nonce=g.nonce)
    except Exception as e:
        return f"An Error Occurred: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@usersblue.route("/usersdelete",
                 methods=['POST', 'DELETE'],
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
        decoded_data = decode_jwt_token(jwt_token)
        # Get the id
        id = request.form.get('id')
        target_ref = users_ref.document(request.form.get('id'))
        existing_user = target_ref.get().to_dict() or {}
        # Update the editable user attributes while preserving identity fields.
        data = {
            u'url': request.form.get('url'),
            u'given_name': request.form.get('given_name'),
            u'family_name': request.form.get('family_name'),
            u'email': request.form.get('email'),
            u'phone': request.form.get('phone'),
            u'designation': request.form.get('designation'),
            u'nro': request.form.get('nro'),
            u'role': request.form.get('role') if request.form.get('role') in {'User', 'Administrator'} else 'User',
            # Removed separate assigned_counter_id field in favor of updating Counter documents
            u'disabled': False,
            u'user': existing_user.get('user') or existing_user.get('name'),
            u'uuid': existing_user.get('uuid'),
            u'customer_id': existing_user.get('customer_id'),
            u'updated_by': decoded_data.get('email') or decoded_data.get('name')
        }

        # Update User Details
        target_ref.update(data)
        
        # Handle counter assignments for the target user.
        target_user_doc = users_ref.document(id).get()
        target_user_data = target_user_doc.to_dict()
        target_uuid = target_user_data.get('uuid')
        target_name = f"{request.form.get('given_name')} {request.form.get('family_name')}"
        
        # 2. Get list of selected counter IDs from form
        selected_counter_ids = request.form.getlist('assigned_counter_ids')
        
        # 3. Find all counters CURRENTLY owned by this user
        current_owned_query = counter_ref.where('uuid', '==', target_uuid).stream()
        current_owned_ids = [c.id for c in current_owned_query]
        
        # 4. Determine Unassign (Owned but not in selected)
        to_unassign = set(current_owned_ids) - set(selected_counter_ids)
        for c_id in to_unassign:
            counter_ref.document(c_id).update({
                'uuid': None,
                'user': None
            })
            
        # 5. Determine Assign (Selected)
        # We update ALL selected to ensure they point to this user (even if already owned, to update Name if changed)
        for c_id in selected_counter_ids:
            counter_ref.document(c_id).update({
                'uuid': target_uuid,
                'user': target_name
            })
            
        # --- Handle API Key Assignments ---
        from system.firstoredb import apikeys_ref
        
        # 1. Get selected API Keys
        selected_apikey_ids = request.form.getlist('assigned_apikey_ids')
        
        # 2. Find all keys CURRENTLY owned by this user
        current_owned_keys_query = apikeys_ref.where('user_uuid', '==', target_uuid).stream()
        current_owned_key_ids = [k.id for k in current_owned_keys_query]
        
        # 3. Unassign keys that were deselected
        # Note: Unassigning a key usually just means removing the user link or disabling it?
        # User request says: "the uuid for the apikey should be updated"
        # We will set user_uuid to None or similar if unassigned? 
        # Or maybe we just leave them orphan. Let's orphan them to be safe.
        to_unassign_keys = set(current_owned_key_ids) - set(selected_apikey_ids)
        for k_id in to_unassign_keys:
            apikeys_ref.document(k_id).update({
                'user_uuid': None,
                'owner_name': firestore.DELETE_FIELD,
                'owner_email': firestore.DELETE_FIELD,
            })
            
        # 4. Assign selected keys
        for k_id in selected_apikey_ids:
            # We assign them to this user
            apikeys_ref.document(k_id).update({
                'user_uuid': target_uuid,
                'owner_name': target_name,
                'owner_email': request.form.get('email'),
            })

        return redirect(url_for('usersblue.userslist'))
    except Exception as e:
        return f"An Error Occurred: {e}"

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
                 methods=['POST'],
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

    return jsonify({
        'success': False,
        'message': 'Password changes are managed by the configured identity provider.'
    }), 501


@usersblue.route("/admin/operations", methods=['GET'])
@login_is_required
@admin_required
def admin_ops():
    return render_template('admin_ops.html', nonce=g.nonce)

@usersblue.route("/admin/fix-uuids", methods=['POST'])
@login_is_required
@admin_required
def run_fix_uuids():
    try:
        # Get all user documents
        docs = users_ref.stream()
        count = 0
        
        for doc in docs:
            user_data = doc.to_dict()
            user_id = doc.id
            
            # Generate a new UUID
            new_uuid = str(uuid.uuid4())
            
            # Update the user document
            users_ref.document(user_id).update({
                'uuid': new_uuid
            })
            count += 1
            
        flash(f'Successfully updated UUIDs for {count} users.')
    except Exception as e:
        flash(f'Error updating UUIDs: {str(e)}')
        
    return redirect(url_for('usersblue.admin_ops'))

@usersblue.route("/admin/auto-link-counters", methods=['POST'])
@login_is_required
@admin_required
def auto_link_counters():
    try:
        # 1. Fetch all users
        users = [u.to_dict() for u in users_ref.stream()]
        
        # 2. Fetch all counters
        counters = [(c.id, c.to_dict()) for c in counter_ref.stream()]
        
        matched_count = 0
        
        # 3. Iterate Counters and try to match
        for c_id, c_data in counters:
            contact = c_data.get('contactpoint')
            if not contact:
                continue
            
            contact_str = str(contact).strip()
            match = None
            
            # Check if it looks like an email
            if '@' in contact_str:
                # Match by Email
                contact_lower = contact_str.lower()
                for u in users:
                    u_email = u.get('email', '').strip().lower()
                    if u_email == contact_lower:
                        match = u
                        break
            else:
                # Match by Name (First Last)
                contact_lower = contact_str.lower()
                for u in users:
                    # Construct full name: "Firstname Lastname"
                    fullname = f"{u.get('given_name', '')} {u.get('family_name', '')}".strip()
                    if fullname.lower() == contact_lower:
                        match = u
                        break
            
            if match and match.get('uuid'):
                # Update Counter with new owner info
                counter_ref.document(c_id).update({
                    'uuid': match['uuid'],
                    # Update the 'user' field to the User's actual name to ensure consistency
                    'user': f"{match.get('given_name', '')} {match.get('family_name', '')}"
                })
                matched_count += 1
                
        flash(f'Successfully linked {matched_count} counters to users based on name match.')
        
    except Exception as e:
        flash(f'Error linking counters: {str(e)}')
        
    return redirect(url_for('usersblue.admin_ops'))


@usersblue.route('/admin/admin_login-config',
                 methods=['GET', 'POST'],
                 endpoint='admin_login_config')
@login_is_required
@admin_required
def admin_login_config():
    if request.method == 'POST':
        new_config = {
            'okta_login_enabled': 'okta_login' in request.form,
            'odc_login_enabled': 'odc_login' in request.form,
            'google_login_enabled': 'google_login' in request.form,
        }
        if not any(new_config.values()):
            flash('At least one login provider must remain enabled', 'error')
            return redirect(url_for('usersblue.admin_login_config'))
        login_config_ref.document('config').set(new_config, merge=True)
        log_activity('updated', 'login configuration', 'config')
        flash('Login configuration updated successfully')
        return redirect(url_for('usersblue.admin_login_config'))

    config = get_login_config()
    return render_template('loginconfig.html', config=config)


def get_login_config():
    default_config = {
        'okta_login_enabled': False,
        'odc_login_enabled': False,
        'google_login_enabled': True,
    }
    try:
        doc = login_config_ref.document('config').get()
        if doc.exists:
            default_config.update(doc.to_dict() or {})
    except Exception:
        logging.exception('Unable to load login configuration')
    return default_config


PAGE_PERMISSION_OPTIONS = [
    ('allowed_list', 'Allowed Domain List'),
    ('disallowed_list', 'Disallowed URL Patterns List'),
]


@usersblue.route('/admin/page-permissions', methods=['GET', 'POST'], endpoint='page_permissions')
@login_is_required
@admin_required
def page_permissions():
    if request.method == 'POST':
        for page_key, _ in PAGE_PERMISSION_OPTIONS:
            roles = ['Administrator']
            if request.form.get(f'{page_key}_user'):
                roles.append('User')
            page_permissions_ref.document(page_key).set({'roles': roles}, merge=True)
        log_activity('updated', 'page permissions', 'settings-pages')
        flash('Page permissions updated successfully')
        return redirect(url_for('usersblue.page_permissions'))

    permissions = {}
    for page_key, _ in PAGE_PERMISSION_OPTIONS:
        snapshot = page_permissions_ref.document(page_key).get()
        permissions[page_key] = (
            (snapshot.to_dict() or {}).get('roles', ['User', 'Administrator'])
            if snapshot.exists else ['User', 'Administrator']
        )
    return render_template(
        'page_permissions.html',
        pages=PAGE_PERMISSION_OPTIONS,
        permissions=permissions,
    )

@usersblue.route('/admin/secrets', methods=['GET', 'POST'], endpoint='admin_secrets')
@login_is_required
@admin_required
def admin_secrets():
    from system.getsecret import getsecrets, store_secret
    
    # Define the list of secrets we want to manage via the UI
    managed_secrets = [
        'client_secret_key', 'client_secret_file',
        'odc_client_id', 'odc_client_secret', 'odc_issuer',
        'okta_client_id', 'okta_client_secret', 'okta_issuer',
        'restrciteddomain'
    ]
    
    if request.method == 'POST':
        secret_name = request.form.get('secret_name')
        secret_value = request.form.get('secret_value')
        
        logging.info(f"Admin attempt to update secret '{secret_name}'")
        
        if secret_name in managed_secrets and secret_value:
            try:
                store_secret(secret_name, secret_value, project_id)
                log_activity('updated', 'system secret', secret_name)
                logging.info(f"Secret '{secret_name}' update called successfully.")
                flash(f"Secret '{secret_name}' updated successfully.")
            except Exception as e:
                logging.exception("Unable to update Secret Manager secret '%s'", secret_name)
                flash('The secret could not be updated. Check Cloud Run permissions and logs.', 'error')
        else:
            logging.warning(f"Invalid secret update attempt: name={secret_name}, has_value={bool(secret_value)}")
            flash("Invalid secret name or value.", "error")
            
        return redirect(url_for('usersblue.admin_secrets'))

    # Fetch current values for all managed secrets
    secret_values = {}
    for name in managed_secrets:
        secret_values[name] = getsecrets(name, project_id)

    return render_template('admin_secrets.html', 
                         managed_secrets=managed_secrets,
                         secret_values=secret_values)
