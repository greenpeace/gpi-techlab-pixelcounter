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
import jwt

from system.getsecret import getsecrets
# Wrtite to Google Cloiud Storage
from google.cloud import storage
from modules.auth.auth import login_is_required

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

        # Attempt to handle named color or hex values
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
    qrcodefilename = (f'{request.form.get("qrcodename").replace(" ", "_")}.png')
    try:
        # Creating an instance of qrcode
        qr = qrcode.QRCode(
                version=1,
                box_size=(int)(request.form.get('boxsize')),
                border=(int)(request.form.get('border')))

        qr.add_data(request.form.get('qrcode'))
        qr.make(fit=True)

        # Process colors, allowing both RGB hex and named colors
        fill_color = get_color(request.form.get('fill_color', ''), 'black')
        back_color = get_color(request.form.get('back_color', ''), 'white')

        # Debug: Print the fill and back colors to check what is being used
        print(f"Fill color: {fill_color}, Back color: {back_color}")

        img = qr.make_image(fill_color=fill_color, back_color=back_color)

        img.save(qrcodefilename)

        # Set up a connection to your Google Cloud Storage bucket
        client = storage.Client()
        bucket = client.bucket(bucketname)

        # Open the image file you want to save to Cloud Storage
        with open(qrcodefilename, "rb") as file:
            # Create a new Cloud Storage blob
            blob = bucket.blob(f'qrcode/{qrcodefilename}')
            # Upload the image file to the blob
            blob.upload_from_file(file)

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

        data = {
            u'active': True,
            u'date_created': datenow(),
            u'filenameurl': f'https://storage.googleapis.com/pixelcounter_bucket/qrcode/{qrcodefilename}',
            u'filename': qrcodefilename,
            u'qrcodename': request.form.get('qrcodename'),
            u'description': request.form.get('description'),
            u'type': request.form.get('type'),
            u'campaign': request.form.get('campaign'),
            u'qrcode': request.form.get('qrcode'),
            u'version': (int)(request.form.get('version')),
            u'boxsize': (int)(request.form.get('boxsize')),
            u'border': (int)(request.form.get('border')),
            u'fill_color': request.form.get('fill_color'),
            u'back_color': request.form.get('back_color'),
            u'uuid': decoded_data.get('google_id'),
            u'user': decoded_data.get('name')
        }

        qrcode_ref.document().set(data)
        # Remove local file
        os.remove(qrcodefilename)
        flash('Data Succesfully Submitted')
        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('qrcodeblue.qrcode'))
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
    try:
        id = request.form['id']
        qrcode_ref.document(id).update(request.form)
        qrcodefilename = (f'{request.form.get("qrcodename")}.png')

        # Creating an instance of qrcode

        qr = qrcode.QRCode(
                version=1,
                box_size=(int)(request.form.get('boxsize')),
                border=(int)(request.form.get('border')))
        qr.add_data(request.form.get('qrcode'))
        qr.make(fit=True)
        img = qr.make_image(fill=request.form.get('fill_color'),
                            back_color=request.form.get('back_color'))
        img.save(qrcodefilename)

        # Set up a connection to your Google Cloud Storage bucket
        client = storage.Client()
        bucket = client.bucket(bucketname)

        # Open the image file you want to save to Cloud Storage
        with open(qrcodefilename, "rb") as file:
            # Create a new Cloud Storage blob
            blob = bucket.blob('qrcode/' + '{qrcodefilename}')
            # Upload the image file to the blob
            blob.upload_from_file(file)

        # Remove local file
        os.remove(qrcodefilename)
        # Return to the list
        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        return f"An Error Occured: {e}"
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
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

        # Check if ID was passed to URL query
        id = request.args.get('id')
        if id:
            qrcodelink = qrcode_ref.document(id).get()
            return jsonify(u'{}'.format(qrcodelink.to_dict()['count'])), 200
        else:
            all_qrcodelinks = []
            # Firestore where with or
            for doc in qrcode_ref.where("uuid", "==",
                                        decoded_data.get('google_id')).where('type', '==', 'local').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                all_qrcodelinks.append(don)

            for doc in qrcode_ref.where('type', '==', 'global').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                all_qrcodelinks.append(don)

            return render_template('qrcode.html', output=all_qrcodelinks)
    except Exception as e:
        return f"An Error Occured: {e}"

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
        ngo = qrcodelink.to_dict()
        return render_template('qrcodeedit.html', **locals())
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@qrcodeblue.route("/qrcodedelete",
                  methods=['GET', 'DELETE'],
                  endpoint='qrcodedelete')
def qrcodedelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        qrcodelink = qrcode_ref.document(id).get()
        ngo = qrcodelink.to_dict()
        qrcode_ref.document(id).delete()
        # Delete the google cloud storage file
        bucket_name = bucketname

        storage_client = storage.Client()

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob('qrcode/' + ngo['filename'])
        blob.delete()

        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@qrcodeblue.route("/qrcodeactive",
                  methods=['GET', 'DELETE'],
                  endpoint='qrcodeactive')
def qrcodeactive():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        qrcodelink = qrcode_ref.document(id).get()
        qrcodeactive = qrcodelink.to_dict()

        # Update flag that translation done
        if qrcodeactive['active'] is True:
            data = {
                u'active': False,
            }
        else:
            data = {
                u'active': True,
            }
        qrcode_ref.document(id).update(data)
        return redirect(url_for('qrcodeblue.qrcode'))
    except Exception as e:
        return f"An Error Occured: {e}"
