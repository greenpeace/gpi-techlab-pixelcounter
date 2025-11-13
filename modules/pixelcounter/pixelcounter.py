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
from system.firstoredb import (
    emailhash_ref,
    counter_ref,
    allowedorigion_ref,
    disallowedorigion_ref
)
from modules.auth.auth import (
    login_is_required,
    require_valid_api_key,
    rate_limit,
    validate_api_key
)
# Install Google Libraries
from google.cloud.firestore import Increment
import google.cloud.logging
# Import logging
import logging
import ipaddress
from datetime import datetime
import jwt
import re

from urllib.parse import urlparse
from ipaddress import ip_address, IPv6Address

# Instantiates a client
client = google.cloud.logging.Client()
client.setup_logging()
logger = client.logger('pixelcounter')

pixelcounterblue = Blueprint('pixelcounterblue',
                             __name__, template_folder='templates')

CORS(pixelcounterblue)


def get_request_context():
    """Extract common request data."""
    remote_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if remote_address:
        remote_address = remote_address.split(',')[0].strip()

    # Normalize IPv4-mapped IPv6
    try:
        ip_obj = ipaddress.ip_address(remote_address)
        if ip_obj.version == 6 and ip_obj.ipv4_mapped:
            remote_address = str(ip_obj.ipv4_mapped)
    except ValueError:
        pass

    referrer_url = request.headers.get('Referer')
    if referrer_url:
        parsed = urlparse(referrer_url)
        domain, path = parsed.netloc.split(':')[0], parsed.path
    else:
        domain, path, referrer_url = None, None, None

    return remote_address, domain, path, referrer_url


def is_gtm_request(req):
    """
    Detect if the request is likely coming from Google Tag Manager.
    """
    ref = req.headers.get("Referer", "")
    return (
        "googletagmanager.com" in ref
        or "gtm" in req.args
        or "_gl" in req.args
        or (req.remote_addr and req.remote_addr.startswith(("35.", "64.233.", "2001:4860:")))
    )


def normalize_domain(domain):
    """Lowercase, remove 'www.' prefix for comparison."""
    if domain:
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    return domain


def normalize_ip(ip):
    """Convert IPv6-mapped IPv4 addresses to plain IPv4."""
    try:
        addr = ip_address(ip)
        if isinstance(addr, IPv6Address) and addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(addr)
    except ValueError:
        return ip


def is_allowed_request(referrer_domain, remote_address, referrer_path):
    """Check Firestore allowed/disallowed lists, allowing API key override but still validating disallowed patterns."""
    allowed_origins = [d.to_dict() for d in allowedorigion_ref.stream()]
    disallowed_patterns = [d.to_dict().get('pattern') for d in disallowedorigion_ref.stream()]

    # --- Step 1: Check API key override ---
    provided_api_key = request.args.get('apikey') or request.headers.get('X-API-Key')
    if provided_api_key:
        valid, reason = validate_api_key(provided_api_key)
        if valid:
            # Still block disallowed patterns
            for pattern in disallowed_patterns:
                if referrer_path and pattern in referrer_path:
                    return False, "Referrer path not allowed (blocked pattern)"
            return True, None
        else:
            # Invalid API key = continue normal checks
            pass

    # --- Step 3: Otherwise, check allowed origins (domain/IP) ---
    allowed = any(
        ('domain' in o and o['domain'] == referrer_domain) or
        ('ipaddress' in o and normalize_ip(o['ipaddress']) == normalize_ip(remote_address))
        for o in allowed_origins
    )

    if not allowed:
        return False, "Not in allowed list"

    # --- Step 4: Always check disallowed patterns ---
    for pattern in disallowed_patterns:
        if referrer_path and pattern in referrer_path:
            return False, "Referrer path not allowed"

    return True, None


def process_email_hash(name, email_hash):
    """Prevent double counting by checking both name and email hash combination."""
    if not name or not email_hash:
        # Missing required identifiers, skip counting
        return False

    # Query for existing record with same name and email_hash combination
    existing = (
        emailhash_ref
        .where("name", "==", name)
        .where("email_hash", "==", email_hash)
        .limit(1)
        .get()
    )

    if existing:
        # A record already exists → duplicate → don't count
        return True

    # Otherwise record this combination so next time it’s blocked
    emailhash_ref.document().set({
        "name": name,
        "email_hash": email_hash,
        "created_at": datetime.utcnow()
    })

    return False


def increment_counter(name, amount=1):
    """Increment counter and totals in Firestore."""
    counter_docs = counter_ref.where('name', '==', name).limit(1).get()
    if not counter_docs:
        return False
    counter_doc = counter_docs[0]
    totals_docs = counter_ref.where('name', '==', 'totals').limit(1).get()
    totals_doc = totals_docs[0] if totals_docs else None

    counter_ref.document(counter_doc.id).update({'count': Increment(amount)})
    if totals_doc:
        counter_ref.document(totals_doc.id).update({'count': Increment(1)})
    return True


def handle_count_request(is_pixel=False):
    """Unified handler for count endpoints."""
    try:
        remote_address, domain, path, referrer = get_request_context()

        # --- Debug and GTM detection section ---
        gtm_involved = is_gtm_request(request)
        print("\n=== Incoming request debug ===")
        print("Remote IP:", remote_address)
        print("Domain:", domain)
        print("Path:", path)
        print("Referrer:", referrer)
        print("Request args:", request.args)
        print("Request headers:", dict(request.headers))
        print("GTM involved?", gtm_involved)
        print("================================\n")
        # ----------------------------------------

        allowed, reason = is_allowed_request(domain, remote_address, path)
        if not allowed:
            logging.info(reason)
            return reason, 400

        name = request.args.get('id')
        amount = int(request.args.get('donation', 1))

        email_hash = request.args.get('email_hash')
        if process_email_hash(name, email_hash):
            return jsonify({"message": "Counter + Email_Hash exist - Already counted"}), 200

        if not increment_counter(name, amount):
            return jsonify({"message": "Counter not found"}), 404

        if is_pixel:
            return send_file('static/images/onepixel.gif', mimetype='image/gif')
        else:
            return jsonify({"success": True}), 200

    except Exception as e:
        logging.exception("Error in count handler")
        return f"An error occurred: {e}", 500


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
@login_is_required
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
@login_is_required
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
@pixelcounterblue.route('/count_pixel', methods=['GET', 'POST'])
@cross_origin()
def count_pixel():
    return handle_count_request(is_pixel=True)


#
# API Route Increase Counter by ID - requires json file body with id and count
# API endpoint /counter
# json {"id":"GP Canada","count", 0}
#
@pixelcounterblue.route("/counter",
                        methods=['POST', 'PUT'])
@cross_origin()
def counter():
    return handle_count_request(is_pixel=False)


##
# The count route used for pixel image to increase a count using a GET request
# API endpoint /count?id=<id>
##
@pixelcounterblue.route("/count",
                        methods=['GET', 'POST',])
@cross_origin()
def count():
    return handle_count_request(is_pixel=False)


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
@login_is_required
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
@login_is_required
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
@login_is_required
def delete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        counter_ref.document(id).delete()
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"


# --- API endpoint ---
@pixelcounterblue.route("/api/createcounter",
                        methods=["POST"],
                        endpoint='create_counter')
@require_valid_api_key
@rate_limit()
def create_counter():

    # --- 1. Validate JSON payload ---
    data = request.get_json(silent=True)
    if not data or "name" not in data:
        return jsonify({"error": "Invalid request payload. 'name' is required."}), 400

    counter_name = data["name"]
    if not re.match(r"^[A-Za-z0-9_]+$", counter_name):
        return jsonify({"error": "Invalid counter name. Only alphanumeric characters and underscores allowed."}), 422

    # --- 3. Check if counter exists ---
    existing = counter_ref.document(counter_name).get()
    if existing.exists:
        return jsonify({"error": "Counter already exists"}), 409

    # --- 4. Create counter ---
    try:
        record = {
            "campaign": data.get("campaign", ""),
            "contactpoint": data.get("contactpoint", ""),
            "count": data.get("count", 0),
            "name": counter_name,
            "nro": data.get("nro", ""),
            "type": data.get("type", "local"),
            "url": data.get("url", ""),
            "user": data.get("user", ""),
            "uuid": data.get("uuid", "")
        }
        counter_ref.document(counter_name).set(record)
        return jsonify({
            "message": "Counter created successfully",
            "counter_name": counter_name
        }), 201
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500
