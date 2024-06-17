import base64
# Get the Flask Files Required
from flask import (
    Blueprint,
    request,
    session,
    send_file,
    jsonify,
    url_for,
    redirect,
    render_template,
    flash
)
from flask_cors import CORS, cross_origin
# firestore collection
from system.firstoredb import counter_ref
from system.firstoredb import allowedorigion_ref
from system.firstoredb import disallowedorigion_ref
from system.firstoredb import emailhash_ref
from system.utils import resolve_ip_from_domain
from modules.auth.auth import login_is_required
# Install Google Libraries
from google.cloud.firestore import Increment
import google.cloud.logging
# Import logging
import logging
import jwt
from urllib.parse import urlparse
# Instantiates a client
client = google.cloud.logging.Client()
client.setup_logging()
logger = client.logger('pixelcounter')

pixelcounterblue = Blueprint('pixelcounterblue',
                             __name__, template_folder='templates')

CORS(pixelcounterblue)


@pixelcounterblue.route("/getsignups",
                        endpoint='getsignups')
@login_is_required
def getsignups():
    return render_template('signups.html', **locals())


@pixelcounterblue.route("/get_my_ip",
                        methods=["GET"])
def get_my_ip():
    return jsonify({'ip': request.remote_addr}), 200

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/add",
                        methods=['POST'],
                        endpoint='create')
@login_is_required
def create():
    try:
        counter_ref.document.set(request.json)
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route add with GET a counter by ID
# - requires json file body with id and count
#   /addset?id=<id>&count=<count>
#


@pixelcounterblue.route("/addset",
                        methods=['GET'],
                        endpoint='createset')
@login_is_required
def createset():
    try:
        counter_id = request.args.get('id')
        counter_ref.document(counter_id).set(request.args)
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/addlist",
                        methods=['GET'],
                        endpoint='addlist')
@login_is_required
def addlist():
    return render_template('listadd.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/documentation",
                        methods=['GET'],
                        endpoint='documentation')
@login_is_required
def documentation():
    return render_template('documentation.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/testincrementiframe",
                        methods=['GET'],
                        endpoint='testincrementiframe')
@login_is_required
def testincrementiframe():
    return render_template('test-display-iframe.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/testincrementimage",
                        methods=['GET'],
                        endpoint='testincrementimage')
@login_is_required
def testincrementimage():
    return render_template('test-increment-image.html', **locals())


#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/testincrementscript",
                        methods=['GET'],
                        endpoint='testincrementscript')
@login_is_required
def testincrementscript():
    return render_template('test-increment-script.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/testodometer",
                        methods=['GET'],
                        endpoint='testodometer')
@login_is_required
def testodometer():
    return render_template('test-odometer.html', **locals())


#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/createlist",
                        methods=['POST'],
                        endpoint='createlist')
@login_is_required
def createlist():
    try:

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token,
                                  'secret_key',
                                  algorithms=['HS256'])

        # Check if id already exixst # check if short exist
        docshort = counter_ref.where('name',
                                     '==',
                                     request.form.get('name')).get()
        if (len(list(docshort))):
            flash('An Error Occured: The counter name has already been taken')
            return redirect(url_for('pixelcounterblue.read'))
        else:
            data = {
                u'name': request.form.get('name'),
                u'nro': request.form.get('nro'),
                u'url': request.form.get('url'),
                u'count': int(request.form.get('count')),
                u'contactpoint': request.form.get('contactpoint'),
                u'campaign': request.form.get('campaign'),
                u'type': request.form.get('type'),
                u'uuid': decoded_data.get('google_id'),
                u'user': decoded_data.get('name')
            }

            counter_ref.document().set(data)
            flash('Data Succesfully Submitted')
            return redirect(url_for('pixelcounterblue.read'))
    except Exception as e:
        flash('An Error Occvured', {e})
        return redirect(url_for('pixelcounterblue.addlist'))

#
# API Route list all or a speific counter by ID
# - requires json file body with id and count
#


@pixelcounterblue.route("/list",
                        methods=['GET'],
                        endpoint='read')
@login_is_required
def read():
    try:

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token,
                                  'secret_key',
                                  algorithms=['HS256'])

        # Check if ID was passed to URL query
        id = request.args.get('id')
        if id:
            counter = counter_ref.document(id).get()
            return jsonify(u'{}'.format(counter.to_dict()['count'])), 200
        else:
            all_counters = []

            for doc in counter_ref.where("uuid", "==",
                                         decoded_data.get('google_id')).where('type', '==', 'local').stream():
                don = doc.to_dict()
                don["id"] = doc.id
                all_counters.append(don)

            for doc in counter_ref.where('type', '==', 'global').stream():
                don = doc.to_dict()
                don["id"] = doc.id
                all_counters.append(don)

            return render_template('list.html', output=all_counters)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route list all or a speific counter by ID
# - requires json file body with id and count
#


@pixelcounterblue.route("/listedit",
                        methods=['GET'],
                        endpoint='listedit')
@login_is_required
def listedit():
    try:
        lists = []
        # Check if ID was passed to URL query
        id = request.args.get('id')
        counterlist = counter_ref.document(id).get()
        don = counterlist.to_dict()
        don["id"] = counterlist.id
        lists.append(don)

        return render_template('listedit.html', ngo=don)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/listdelete",
                        methods=['GET', 'DELETE'])
def listdelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        counter_ref.document(id).delete()
        return redirect(url_for('pixelcounterblue.read'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@pixelcounterblue.route("/update",
                        methods=['POST', 'PUT'])
def update():
    try:
        id = request.json['id']
        counter_ref.document(id).update(request.json)
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@pixelcounterblue.route("/updateform",
                        methods=['POST', 'PUT'],
                        endpoint='updateform')
@login_is_required
def updateform():
    try:

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token,
                                  'secret_key',
                                  algorithms=['HS256'])

        id = request.form['id']

        data = {
            u'name': request.form.get('name'),
            u'nro': request.form.get('nro'),
            u'url': request.form.get('url'),
            u'count': int(request.form.get('count')),
            u'contactpoint': request.form.get('contactpoint'),
            u'campaign': request.form.get('campaign'),
            u'type': request.form.get('type'),
            u'uuid': decoded_data.get('google_id'),
            u'user': decoded_data.get('name')
        }
        counter_ref.document(id).update(data)
        return redirect(url_for('pixelcounterblue.read'))
    except Exception as e:
        flash(f"An Error Occured: {e}")
        return redirect(url_for('pixelcounterblue.listedit'))

#
# API Route Increase Counter by ID - requires json file body with id and count
# API endpoint /counter
# json {"id":"GP Canada","count", 0}
#


@pixelcounterblue.route('/count_pixel',
                        methods=['GET', 'POST',])
@cross_origin()
def count_pixel():
    try:
        # Check if Remote Host is in the allowed list
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict())

        # check if the allowed url matches a pattern in disallowed list
        disallowed_patterns = []
        for disdoc in disallowedorigion_ref.stream():
            disallowed_patterns.append(disdoc.to_dict().get('pattern'))

        remote_address = None

        # Check if HTTP_X_FORWARDED_FOR is set
        if 'HTTP_X_FORWARDED_FOR' in request.environ:
            forwarded_for = request.environ['HTTP_X_FORWARDED_FOR']
            # Split the forwarded for string to get the actual IP address
            remote_address = forwarded_for.split(',')[0]

        # If HTTP_X_FORWARDED_FOR is not set or not allowed, use REMOTE_ADDR
        if remote_address is None and 'REMOTE_ADDR' in request.environ:
            remote_address = request.environ['REMOTE_ADDR']

        # Get the referrer from the 'Referer' header
        referrer_url = request.headers.get('Referer')

        if referrer_url:
            parsed_referrer = urlparse(referrer_url)
            referrer_domain = parsed_referrer.netloc.split(':')[0]
            referrer_path = parsed_referrer.path
        else:
            referrer_domain = None
            referrer_path = None

        # Now remote_address contains the appropriate remote address
        if remote_address is not None:
            # Check if the request domain matches
            # any domain in the allowed list
            for allowed_origin in allowed_origin_list:
                if ('domain' in allowed_origin and referrer_domain == allowed_origin['domain']) or \
                        ('ipaddress' in allowed_origin and remote_address == allowed_origin['ipaddress']):
                    # Check if referrer path matches any disallowed patterns
                    for pattern in disallowed_patterns:
                        if referrer_path is not None and pattern in referrer_path:
                            # Log and reject the request
                            logging.info("Disallowed URL accessed")
                            return "Referrer path not allowed", 403
                    # On allowed lsut, check if ID was passed to URL query
                    email_hash = request.args.get('email_hash')
                    if email_hash is not None:
                        docRef = emailhash_ref.where('email_hash',
                                                     '==',
                                                     email_hash).get()
                        documents = [d for d in docRef]
                        # Check if hash value already exixsts in the database
                        if len(documents):
                            # If exists, don not increase count by 1
                            return '', 200
                        else:
                            # Add hashed email to database
                            data = {
                                u'email_hash': email_hash,
                            }
                            emailhash_ref.document().set(data)
                    # Add Counter
                    name = request.args.get('id')  # Get name from request parameter

                    # Construct Firestore query to find the counter document
                    docRef = counter_ref.where('name', '==', name).limit(1).get()

                    documents = [d for d in docRef]
                    # Check if hash value already exixsts in the database
                    if not len(documents):
                        return 'Counter not found', 404  # Return error if no document found

                    # Define a query to find the document with name "totals"
                    totals_ref = counter_ref.where('name', '==', 'totals').limit(1).get()  # Limit to 1 document

                    totalsdoc = [d for d in totals_ref]

                    # Access the first document (assuming unique names)
                    counter_doc = docRef[0]
                    totals_doc = totalsdoc[0]

                    amount = request.args.get('donation')
                    if amount is not None:
                        # Convert amount to integer
                        amount_int = int(amount)
                        counter_ref.document(counter_doc.id).update({u'count': Increment(amount_int)})
                        # Check if the document exists
                        if len(totalsdoc):
                            # Update the "count" field in the totals document
                            counter_ref.document(totals_doc.id).update({u'count': Increment(1)})
                        else:
                            # Handle the case where the
                            # document is not found (optional)
                            print('Totals counter not found')
                            return "Totals counter not found", 400
                    else:
                        counter_ref.document(counter_doc.id).update({u'count': Increment(1)})
                        # Check if the document exists
                        if len(totalsdoc):
                            # Update the "count" field in the totals document
                            counter_ref.document(totals_doc.id).update({u'count': Increment(1)})
                        else:
                            # Handle the case where the document is not found (optional)
                            print('Totals COunter not found')
                            return "Totals Counter not found", 400

                    filename = 'static/images/onepixel.gif'
                    return send_file(filename, mimetype='image/gif')
        # Add a default response if none of the conditions are met
        logging.info("No Match Referrer not in Allowed Lists")
        return "No match referrer not in allowed list", 400
    except Exception as e:
        return f"An Error Occured: {e}", 500

#
# API Route Increase Counter by ID - requires json file body with id and count
# API endpoint /counter
# json {"id":"GP Canada","count", 0}
#


@pixelcounterblue.route("/counter",
                        methods=['POST', 'PUT'])
@cross_origin()
def counter():
    try:
        # Check if Remote Host is in the allowed list
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict())

        # check if the allowed url matches a pattern in disallowed list
        disallowed_patterns = []
        for disdoc in disallowedorigion_ref.stream():
            disallowed_patterns.append(disdoc.to_dict().get('pattern'))

        remote_address = None

        # Check if HTTP_X_FORWARDED_FOR is set
        if 'HTTP_X_FORWARDED_FOR' in request.environ:
            forwarded_for = request.environ['HTTP_X_FORWARDED_FOR']
            # Split the forwarded for string to get the actual IP address
            remote_address = forwarded_for.split(',')[0]

        # If HTTP_X_FORWARDED_FOR is not set or not allowed, use REMOTE_ADDR
        if remote_address is None and 'REMOTE_ADDR' in request.environ:
            remote_address = request.environ['REMOTE_ADDR']

        # Get the referrer from the 'Referer' header
        referrer_url = request.headers.get('Referer')

        if referrer_url:
            parsed_referrer = urlparse(referrer_url)
            referrer_domain = parsed_referrer.netloc.split(':')[0]
            referrer_path = parsed_referrer.path
        else:
            referrer_domain = None
            referrer_path = None

        # Now remote_address contains the appropriate remote address
        if remote_address is not None:
            # Check if the request domain matches any domain in the allowed list
            for allowed_origin in allowed_origin_list:
                if ('domain' in allowed_origin and referrer_domain == allowed_origin['domain']) or \
                        ('ipaddress' in allowed_origin and remote_address == allowed_origin['ipaddress']):
                    # Check if referrer path matches any disallowed patterns
                    for pattern in disallowed_patterns:
                        if referrer_path is not None and pattern in referrer_path:
                            # Log and reject the request
                            logging.info("Disallowed URL accessed")
                            return "Disallowed URL", 403
                    # On allowed lsut, check if ID was passed to URL query
                    email_hash = request.args.get('email_hash')
                    if email_hash is not None:
                        docRef = emailhash_ref.where('email_hash', '==', email_hash).get()
                        documents = [d for d in docRef]
                        # Check if hash value already exixsts in the database
                        if len(documents):
                            # If exists, don not increase count by 1
                            return base64.b64decode(b'='), 200
                        else:
                            # Add hashed email to database
                            data = {
                                u'email_hash': email_hash,
                            }
                            emailhash_ref.document().set(data)
                    # Add Counter
                    name = request.args.get('id')  # Get name from request parameter

                    # Construct Firestore query to find the counter document
                    docRef = counter_ref.where('name', '==', name).limit(1).get()

                    documents = [d for d in docRef]
                    # Check if hash value already exixsts in the database
                    if not len(documents):
                        return 'Document not found', 404  # Return error if no document found

                    # Define a query to find the document with name "totals"
                    totals_ref = counter_ref.where('name', '==', 'totals').limit(1).get()  # Limit to 1 document

                    totalsdoc = [d for d in totals_ref]

                    # Access the first document (assuming unique names)
                    counter_doc = docRef[0]
                    totals_doc = totalsdoc[0]

                    amount = request.args.get('donation')
                    if amount is not None:
                        # Convert amount to integer
                        amount_int = int(amount)
                        counter_ref.document(counter_doc.id).update({u'count': Increment(amount_int)})
                        # Check if the document exists
                        if len(totalsdoc):
                            # Update the "count" field in the totals document
                            counter_ref.document(totals_doc.id).update({u'count': Increment(1)})
                        else:
                            # Handle the case where the
                            # document is not found (optional)
                            print('Totals document not found')
                            return "No counter update", 400

                    else:
                        counter_ref.document(counter_doc.id).update({u'count': Increment(1)})
                        # Check if the document exists
                        if len(totalsdoc):
                            # Update the "count" field in the totals document
                            counter_ref.document(totals_doc.id).update({u'count': Increment(1)})
                        else:
                            # Handle the case where the
                            # document is not found (optional)
                            print('Totals document not found')
                            return "Totals Document not found", 400

                    return jsonify({"success": True}), 200

        logging.info("No Match Allowed Lists")
        return "Not in allowed list", 400

    except Exception as e:
        return f"An Error Occured: {e}", 500

##
# The count route used for pixel image to increase a count using a GET request
# API endpoint /count?id=<id>
##


@pixelcounterblue.route("/count",
                        methods=['GET', 'POST',])
@cross_origin()
def count():
    try:
        # Check if Remote Host is in the allowed list
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict())

        # check if the allowed url matches a pattern in disallowed list
        disallowed_patterns = []
        for disdoc in disallowedorigion_ref.stream():
            disallowed_patterns.append(disdoc.to_dict().get('pattern'))

        try:
            remote_address = None

            # Check if HTTP_X_FORWARDED_FOR is set
            if 'HTTP_X_FORWARDED_FOR' in request.environ:
                forwarded_for = request.environ['HTTP_X_FORWARDED_FOR']
                # Split the forwarded for string to get the actual IP address
                remote_address = forwarded_for.split(',')[0]

            # If HTTP_X_FORWARDED_FOR is not set or not allowed, use REMOTE_ADDR
            if remote_address is None and 'REMOTE_ADDR' in request.environ:
                remote_address = request.environ['REMOTE_ADDR']

            # Get the referrer from the 'Referer' header
            referrer_url = request.headers.get('Referer')

            if referrer_url:
                parsed_referrer = urlparse(referrer_url)
                referrer_domain = parsed_referrer.netloc.split(':')[0]
                referrer_path = parsed_referrer.path
                full_referrer_uri = referrer_url
                referrer_ip = resolve_ip_from_domain(referrer_domain)
            else:
                referrer_domain = None
                referrer_path = None
                full_referrer_uri = None
                referrer_ip = None

            # Log the headers for debugging purposes
            # Use the logger to log messages
            print("Headers: %s", request.headers)
            print("Remote Address: %s", remote_address)
            print("Referrer URL: %s", referrer_url)
            print("Full Referrer URI: %s", full_referrer_uri)
            print("Referrer IP: %s", referrer_ip)
            print("Referrer Domain: %s", referrer_domain)
            print("Referrer Path: %s", referrer_path)

            # Now remote_address contains the appropriate remote address
            if remote_address is not None:
                # On allowed lsut, check if ID was passed to URL query
                # Check if the request domain matches any domain in the allowed list
                for allowed_origin in allowed_origin_list:
                    if ('domain' in allowed_origin and referrer_domain == allowed_origin['domain']) or \
                            ('ipaddress' in allowed_origin and remote_address == allowed_origin['ipaddress']):
                        # Check if referrer path matches any disallowed patterns
                        for pattern in disallowed_patterns:
                            if referrer_path is not None and pattern in referrer_path:
                                # Log and reject the request
                                logging.info("Disallowed URL accessed")
                                return "Disallowed URL", 403

                        # On allowed list, check if ID was passed to URL query
                        email_hash = request.args.get('email_hash')
                        if email_hash is not None:
                            docRef = emailhash_ref.where('email_hash',
                                                         '==',
                                                         email_hash).get()
                            documents = [d for d in docRef]
                            # Check if hash value already
                            # exixsts in the database
                            if len(documents):
                                # If exists, don not increase count by 1
                                logging.info("Email hash Exist")
                                return 'Email hash Exist', 200
                            else:
                                # Add hashed email to database
                                data = {
                                    u'email_hash': email_hash,
                                }
                                emailhash_ref.document().set(data)
                        # Add Counter
                        # Get name from request parameter
                        name = request.args.get('id')

                        # Construct Firestore query
                        # to find the counter document
                        docRef = counter_ref.where('name',
                                                   '==',
                                                   name).limit(1).get()

                        documents = [d for d in docRef]
                        # Check if hash value already exixsts in the database
                        if not len(documents):
                            # Return error if no document found
                            return 'Document not found', 404

                        # Define a query to find the document w
                        # ith name "totals"
                        totals_ref = counter_ref.where('name',
                                                       '==',
                                                       'totals').limit(1).get()

                        totalsdoc = [d for d in totals_ref]

                        # Access the first document (assuming unique names)
                        counter_doc = docRef[0]
                        totals_doc = totalsdoc[0]

                        amount = request.args.get('donation')
                        if amount is not None:
                            # Convert amount to integer
                            amount_int = int(amount)
                            counter_ref.document(counter_doc.id).update({u'count': Increment(amount_int)})
                            # Check if the document exists
                            if len(totalsdoc):
                                # Update the "count" field
                                # in the totals document
                                counter_ref.document(totals_doc.id).update({u'count': Increment(1)})
                            else:
                                # Handle the case where
                                # the document is not found (optional)
                                print('Totals document not found')
                                return "Totals Document not found", 400

                        else:
                            counter_ref.document(counter_doc.id).update({u'count': Increment(1)})
                            # Check if the document exists
                            if len(totalsdoc):
                                # Update the "count" field
                                # in the totals document
                                counter_ref.document(totals_doc.id).update({u'count': Increment(1)})
                            else:
                                # Handle the case where
                                # the document is not found (optional)
                                print('Totals document not found')
                                return "Totals Document not found", 400

                        logging.info("Counter Been Updated")
                        return base64.b64decode(b'='), 200

            # Add a default response if none of the conditions are met
            logging.info("No Match Allowed Lists")
            return "Not in allowed list", 400
        except Exception as e:
            print(e)
            return f"An Error Occured: {e}", 500
    except Exception as e:
        print(e)
        return f"Error no access firestore: {e}", 500

##
# The API endpoint allows the user to get the endpoint total defined  by id
# API endpoint /signup?id=<id>
##


@pixelcounterblue.route("/signup",
                        methods=['POST', 'PUT'],
                        endpoint='signup')
@login_is_required
def signup():
    try:
        if request.method == "POST":
            name = request.form['name']
            docRef = counter_ref.where('name', '==', name).limit(1).get()

            # Check if the query returned any documents
            if docRef:
                # Get the first document from the query result
                doc = docRef[0]
                # Convert the document to a dictionary
                output = f"{ doc.to_dict()['count'] }"
            else:
                # Handle the case where no document is found
                output = None
            return render_template('signups.html', output=output)
        return render_template('signups.html',
                               output="No NRO name has been given")
    except Exception as e:
        return render_template('signups.html',
                               output="An Error Occured: {}" + e)

##
# The API endpoint allows the user to get the endpoint total defined  by id
# API endpoint /signup?id=<id>
##


@pixelcounterblue.route("/signups",
                        methods=['POST', 'GET'],
                        endpoint='signups')
@cross_origin()
def signups():
    try:

        name = request.args.get('id')
        # Construct Firestore query to find the counter document
        docRef = counter_ref.where('name', '==', name).limit(1).get()

        # Check if the query returned any documents
        if docRef:
            # Get the first document from the query result
            doc = docRef[0]
            # Convert the document to a dictionary
            doc_dict = doc.to_dict()
            # Extract the 'count' value from the dictionary
            output = doc_dict['count']
        else:
            # Handle the case where no document is found
            output = None

        return jsonify({"unique_count": output, "id": name}), 200
    except Exception as e:
        return f"An Error Occured: {e}", 500


#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlistadd",
                        methods=['GET'],
                        endpoint='allowedlistadd')
@login_is_required
def allowedlistadd():
    return render_template('allowedlistadd.html', **locals())

#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlist",
                        methods=['GET'],
                        endpoint='allowedlist')
@login_is_required
def allowedlist():
    try:
        allowedlist = []
        for doc in allowedorigion_ref.stream():
            don = doc.to_dict()
            don["id"] = doc.id
            allowedlist.append(don)

        return render_template('allowedlist.html', allowed=allowedlist)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlistcreate",
                        methods=['POST'],
                        endpoint='allowedlistcreate')
@login_is_required
def allowedlistcreate():
    try:
        data = {
            u'name': request.form.get('name'),
            u'domain': request.form.get('domain'),
            u'ipaddress': request.form.get('ipaddress')
        }

        allowedorigion_ref.document().set(data)
        flash('Data Succesfully Submitted')
        return redirect(url_for('pixelcounterblue.allowedlist'))
    except Exception as e:
        flash('An Error Occvured')
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@pixelcounterblue.route("/allowedlistupdate",
                        methods=['POST', 'PUT'],
                        endpoint='allowedlistupdate')
@login_is_required
def allowedlistupdate():
    try:
        id = request.form['id']
        data = {
            u'name': request.form.get('name'),
            u'domain': request.form.get('domain'),
            u'ipaddress': request.form.get('ipaddress')
        }
        allowedorigion_ref.document(id).update(data)
        return redirect(url_for('pixelcounterblue.allowedlist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route list all or a speific counter by ID
# - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlistedit",
                        methods=['GET'],
                        endpoint='allowedlistedit')
@login_is_required
def allowedlistedit():
    try:
        allowedlists = []
        # Check if ID was passed to URL query
        id = request.args.get('id')
        allowedlist = allowedorigion_ref.document(id).get()
        don = allowedlist.to_dict()
        don["id"] = allowedlist.id
        allowedlists.append(don)

        return render_template('allowedlistedit.html', ngo=don)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/allowedlistdelete",
                        methods=['GET', 'DELETE'],
                        endpoint='allowedlistdelete')
def allowedlistdelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        allowedorigion_ref.document(id).delete()
        return redirect(url_for('pixelcounterblue.allowedlist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlistadd",
                        methods=['GET'],
                        endpoint='disallowedlistadd')
@login_is_required
def disallowedlistadd():
    return render_template('disallowedlistadd.html', **locals())

#
# API Route list all or a speific counter by ID
# - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlist",
                        methods=['GET'],
                        endpoint='disallowedlist')
@login_is_required
def disallowedlist():
    try:
        disallowedlist = []
        for doc in disallowedorigion_ref.stream():
            don = doc.to_dict()
            don["id"] = doc.id
            disallowedlist.append(don)

        return render_template('disallowedlist.html', allowed=disallowedlist)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlistcreate",
                        methods=['POST'],
                        endpoint='disallowedlistcreate')
@login_is_required
def disallowedlistcreate():
    try:
        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

        data = {
            u'name': request.form.get('name'),
            u'pattern': request.form.get('pattern'),
            u'uuid': decoded_data.get('google_id'),
            u'user': decoded_data.get('name')
        }

        # Write to Firestore DB
        disallowedorigion_ref.document().set(data)
        flash('Data Succesfully Submitted')
        return redirect(url_for('pixelcounterblue.disallowedlist'))
    except Exception as e:
        flash('An Error Occvured')
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@pixelcounterblue.route("/disallowedlistupdate",
                        methods=['POST', 'PUT'],
                        endpoint='disallowedlistupdate')
@login_is_required
def disallowedlistupdate():
    try:
        id = request.form['id']
        data = {
            u'name': request.form.get('name'),
            u'pattern': request.form.get('pattern')
        }
        disallowedorigion_ref.document(id).update(data)
        return redirect(url_for('pixelcounterblue.disallowedlist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlistedit",
                        methods=['GET'],
                        endpoint='disallowedlistedit')
@login_is_required
def disallowedlistedit():
    try:
        disallowedlists = []
        # Check if ID was passed to URL query
        id = request.args.get('id')
        disallowedlist = disallowedorigion_ref.document(id).get()
        don = disallowedlist.to_dict()
        don["id"] = disallowedlist.id
        disallowedlists.append(don)

        return render_template('disallowedlistedit.html', ngo=don)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/disallowedlistdelete",
                        methods=['GET', 'DELETE'],
                        endpoint='disallowedlistdelete')
def disallowedlistdelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        disallowedorigion_ref.document(id).delete()
        return redirect(url_for('pixelcounterblue.disallowedlist'))
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/delete",
                        methods=['GET', 'DELETE'])
def delete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        counter_ref.document(id).delete()
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"
