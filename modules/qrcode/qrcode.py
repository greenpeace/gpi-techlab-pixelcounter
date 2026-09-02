# Get the Flask Files Required
from flask import (
    Blueprint,
    request,
    session,
    jsonify,
    url_for,
    redirect,
    render_template,
    flash
)

# FQrcode firestore collection
from system.firstoredb import qrcode_ref

from PIL import ImageColor

from system.date import datenow
# locals
import os
import tempfile
import logging
from werkzeug.utils import secure_filename

from system.getsecret import getsecrets
# Wrtite to Google Cloiud Storage
from google.cloud import storage
from modules.auth.auth import login_is_required
from system.activity import log_activity
from system.authorization import can_manage_resource, require_resource_access
from system.jwt_utils import decode_jwt_token

# Import project id
from system.setenv import project_id

bucketname = getsecrets("qrcode-bucket_name", project_id)

# Set Blueprint’s name https://realpython.com/flask-blueprint/
qrcodeblue = Blueprint('qrcodeblue', __name__, template_folder='templates')

# Helper function to process colors


def get_color(color_input, default):
    try:
        color_input = color_input.strip()  # Strip any leading/trailing spaces

        # Check if input is in the form of a tuple like "(155, 255, 75)"
        if color_input.startswith('(') and color_input.endswith(')'):
            color_input = color_input[1:-1].strip()  # Remove parentheses and any surrounding spaces

        # Now check if it's a comma-separated RGB value
        if ',' in color_input:
            # Remove any extra spaces between the numbers and split by comma
            rgb = tuple(map(int, [x.strip() for x in color_input.split(',')]))
            # Ensure we have exactly 3 values and each is between 0 and 255
            if len(rgb) == 3 and all(0 <= val <= 255 for val in rgb):
                return rgb

        # If not RGB, attempt to handle it as a named color or hex code
        return ImageColor.getrgb(color_input)

    except (ValueError, TypeError):
        # If anything goes wrong, return the default color
        return default

# qrcode Section
#
# API Route add a searchlink by ID - requires json file body with id and count
#


@qrcodeblue.route("/qrcodeadd",
                  methods=['GET'],
                  endpoint='qrcodeadd')
@login_is_required
def qrcodeadd():
    return render_template('qrcodeadd.html', **locals())

#
# API Route add a searchlink by ID - requires json file body with id and count
#


@qrcodeblue.route("/qrcodecreate",
                  methods=['POST'],
                  endpoint='qrcodecreate')
@login_is_required
def qrcodecreate():
    import qrcode
    qrcodefilename = f"{secure_filename(request.form.get('qrcodename', '')) or 'qrcode'}.png"
    temporary_path = None
    try:
        qr_content = request.form.get('qrcode', '')
        if not qr_content or len(qr_content) > 4096:
            raise ValueError('QR code content must be between 1 and 4096 characters')
        version = max(1, min(int(request.form.get('version', 1)), 40))
        boxsize = max(1, min(int(request.form.get('boxsize', 10)), 50))
        border = max(0, min(int(request.form.get('border', 4)), 20))
        # Creating an instance of qrcode
        qr = qrcode.QRCode(
                version=version,
                box_size=boxsize,
                border=border)

        qr.add_data(qr_content)
        qr.make(fit=True)

        # Process colors, allowing both RGB hex and named colors
        fill_color = get_color(request.form.get('fill_color', ''), 'black')
        back_color = get_color(request.form.get('back_color', ''), 'white')

        # Debug: Print the fill and back colors to check what is being used
        print(f"Fill color: {fill_color}, Back color: {back_color}")

        img = qr.make_image(fill_color=fill_color, back_color=back_color)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temporary_file:
            temporary_path = temporary_file.name
        img.save(temporary_path)

        # Set up a connection to your Google Cloud Storage bucket
        client = storage.Client()
        bucket = client.bucket(bucketname)

        # Open the image file you want to save to Cloud Storage
        with open(temporary_path, "rb") as file:
            # Create a new Cloud Storage blob
            blob = bucket.blob(f'qrcode/{qrcodefilename}')
            # Upload the image file to the blob
            blob.upload_from_file(file)

        jwt_token = session.get('jwt_token')
        decoded_data = decode_jwt_token(jwt_token)

        data = {
            u'active': True,
            u'date_created': datenow(),
            u'filenameurl': f'https://storage.googleapis.com/{bucketname}/qrcode/{qrcodefilename}',
            u'filename': qrcodefilename,
            u'qrcodename': request.form.get('qrcodename'),
            u'description': request.form.get('description'),
            u'type': request.form.get('type'),
            u'campaign': request.form.get('campaign'),
            u'qrcode': request.form.get('qrcode'),
            u'version': version,
            u'boxsize': boxsize,
            u'border': border,
            u'fill_color': request.form.get('fill_color'),
            u'back_color': request.form.get('back_color'),
            u'uuid': decoded_data.get('google_id'),
            u'user': decoded_data.get('name')
        }

        doc_ref = qrcode_ref.document()
        doc_ref.set(data)
        log_activity('created', 'QR code', doc_ref.id, data.get('qrcodename'))
        # Remove local file
        flash('Data Succesfully Submitted')
        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('qrcodeblue.qrcode'))
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@qrcodeblue.route("/qrcodeupdate",
                  methods=['POST', 'PUT'],
                  endpoint='qrcodeupdate')
@login_is_required
def qrcodeupdate():
    import qrcode
    temporary_path = None
    try:
        id = request.form['id']
        doc_ref = qrcode_ref.document(id)
        old_data = require_resource_access(doc_ref.get())
        qrcodefilename = f"{secure_filename(request.form.get('qrcodename', '')) or 'qrcode'}.png"
        data = {
            'qrcodename': request.form.get('qrcodename'),
            'description': request.form.get('description'),
            'type': request.form.get('type'),
            'campaign': request.form.get('campaign'),
            'qrcode': request.form.get('qrcode'),
            'version': int(request.form.get('version')),
            'boxsize': int(request.form.get('boxsize')),
            'border': int(request.form.get('border')),
            'fill_color': request.form.get('fill_color'),
            'back_color': request.form.get('back_color'),
            'filename': qrcodefilename,
            'filenameurl': f'https://storage.googleapis.com/{bucketname}/qrcode/{qrcodefilename}',
        }
        if not data['qrcode'] or len(data['qrcode']) > 4096:
            raise ValueError('QR code content must be between 1 and 4096 characters')
        data['version'] = max(1, min(data['version'], 40))
        data['boxsize'] = max(1, min(data['boxsize'], 50))
        data['border'] = max(0, min(data['border'], 20))

        # Creating an instance of qrcode

        qr = qrcode.QRCode(
                version=data['version'],
                box_size=data['boxsize'],
                border=data['border'])
        qr.add_data(data['qrcode'])
        qr.make(fit=True)
        img = qr.make_image(fill_color=get_color(data['fill_color'], 'black'),
                            back_color=get_color(data['back_color'], 'white'))
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temporary_file:
            temporary_path = temporary_file.name
        img.save(temporary_path)

        # Set up a connection to your Google Cloud Storage bucket
        client = storage.Client()
        bucket = client.bucket(bucketname)

        # Open the image file you want to save to Cloud Storage
        with open(temporary_path, "rb") as file:
            # Create a new Cloud Storage blob
            blob = bucket.blob(f'qrcode/{qrcodefilename}')
            # Upload the image file to the blob
            blob.upload_from_file(file)

        doc_ref.update(data)
        old_filename = old_data.get('filename')
        if old_filename and old_filename != qrcodefilename:
            bucket.blob(f'qrcode/{old_filename}').delete()
        log_activity('updated', 'QR code', id, data.get('qrcodename'))
        # Return to the list
        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        return f"An Error Occured: {e}"
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@qrcodeblue.route("/qrcode",
                  methods=['GET'],
                  endpoint='qrcode')
@login_is_required
def qrcode():
    try:
        jwt_token = session.get('jwt_token')
        decoded_data = decode_jwt_token(jwt_token)

        # Check if ID was passed to URL query
        id = request.args.get('id')
        if id:
            qrcodelink = qrcode_ref.document(id).get()
            data = require_resource_access(qrcodelink)
            data['docid'] = qrcodelink.id
            return jsonify(data), 200
        else:
            all_qrcodelinks = []
            # Firestore where with or
            for doc in qrcode_ref.where("uuid", "==",
                                        decoded_data.get('google_id')).where('type', '==', 'local').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                don["can_manage"] = can_manage_resource(don)
                all_qrcodelinks.append(don)

            for doc in qrcode_ref.where('type', '==', 'global').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                if doc.id not in {item['docid'] for item in all_qrcodelinks}:
                    don["can_manage"] = can_manage_resource(don)
                    all_qrcodelinks.append(don)

            return render_template('qrcode.html', output=all_qrcodelinks)
    except Exception:
        logging.exception('Unable to list QR codes')
        return render_template('500.html'), 500

#
# API Route list all or a speific searchlink by ID - requires json file body with id and count
#


@qrcodeblue.route("/qrcodeedit",
                  methods=['GET'],
                  endpoint='qrcodeedit')
@login_is_required
def qrcodeedit():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        qrcodelink = qrcode_ref.document(id).get()
        ngo = require_resource_access(qrcodelink)
        return render_template('qrcodeedit.html', **locals())
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@qrcodeblue.route("/qrcodedelete",
                  methods=['POST', 'DELETE'],
                  endpoint='qrcodedelete')
@login_is_required
def qrcodedelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        doc_ref = qrcode_ref.document(id)
        ngo = require_resource_access(doc_ref.get())
        doc_ref.delete()
        # Delete the google cloud storage file
        bucket_name = bucketname

        storage_client = storage.Client()

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob('qrcode/' + ngo['filename'])
        try:
            blob.delete()
        except Exception:
            logging.exception('Unable to delete QR image %s', ngo.get('filename'))
        log_activity('deleted', 'QR code', id, ngo.get('qrcodename'))

        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        logging.exception('Unable to delete QR code')
        return "Unable to delete QR code", 500

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@qrcodeblue.route("/qrcodeactive",
                  methods=['POST'],
                  endpoint='qrcodeactive')
@login_is_required
def qrcodeactive():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        doc_ref = qrcode_ref.document(id)
        qrcodeactive = require_resource_access(doc_ref.get())

        # Update flag that translation done
        if qrcodeactive['active'] is True:
            data = {
                u'active': False,
            }
        else:
            data = {
                u'active': True,
            }
        doc_ref.update(data)
        log_activity(
            'activated' if data['active'] else 'deactivated',
            'QR code',
            id,
            qrcodeactive.get('qrcodename'),
        )
        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        return f"An Error Occured: {e}"
