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
    flash,
    g
)

from flask_cors import CORS, cross_origin
# firestore collection
from system.firstoredb import (
    emailhash_ref,
    counter_ref,
    allowedorigion_ref,
    disallowedorigion_ref,
    users_ref,
    nro_ref,
    documentation_ref
)
from modules.auth.auth import (
    admin_required,
    get_user_data_from_token,
    login_is_required,
    require_valid_api_key,
    rate_limit,
    validate_api_key
)
# Install Google Libraries
from google.cloud.firestore import Increment, SERVER_TIMESTAMP
import google.cloud.logging
# Import logging
import logging
import ipaddress
from datetime import datetime
import re
import hashlib
from google.api_core.exceptions import AlreadyExists

from urllib.parse import urlparse
from ipaddress import ip_address, IPv6Address
from system.activity import log_activity
from system.authorization import can_manage_resource, require_resource_access

# Instantiates a client
client = google.cloud.logging.Client()
client.setup_logging()
logger = client.logger('pixelcounter')

pixelcounterblue = Blueprint('pixelcounterblue',
                             __name__, template_folder='templates')

DEFAULT_DOCUMENTATION_TITLE = 'Pixel Counter Documentation'
DEFAULT_DOCUMENTATION_SUMMARY = 'Create, update, display, and integrate campaign counters.'
DEFAULT_DOCUMENTATION_CONTENT = """## Introduction
Pixel Counter combines petition signatures from Greenpeace campaigns and NROs into shared or local totals.

## Increment a counter
Send a GET request to:

/count?id=<counter_name>

You can optionally include donation=<amount> and email_hash=<encoded_hash>. The email hash prevents the same signup from being counted more than once.

## Read a counter
Send a GET request to:

/signups?id=<counter_name>

The response contains unique_count and id as JSON.

## Create a counter through the API
Send a POST request to /api/createcounter with JSON data and provide the API key in the X-API-Key header. Duplicate counter names return HTTP 409.

## URL shortener
Create short links from the URL Shortener screen. Short names cannot use an existing application route such as count, signup, or login.

## QR codes
Create downloadable QR codes from the QR Code screen. QR content is limited to 4096 characters.

## Testing
Use the testing tools in the Counters menu to verify display and increment integrations before publishing a campaign.
"""


def _documentation_sections(content):
    """Parse safe `## Heading` sections without rendering user-provided HTML."""
    sections = []
    current = None
    for line in str(content or '').splitlines():
        if line.startswith('## '):
            if current:
                current['body'] = '\n'.join(current.pop('lines')).strip()
                sections.append(current)
            heading = line[3:].strip() or 'Section'
            slug = re.sub(r'[^a-z0-9]+', '-', heading.casefold()).strip('-') or 'section'
            current = {'heading': heading, 'slug': slug, 'lines': []}
        else:
            if current is None:
                current = {'heading': 'Overview', 'slug': 'overview', 'lines': []}
            current['lines'].append(line)
    if current:
        current['body'] = '\n'.join(current.pop('lines')).strip()
        sections.append(current)
    return sections

CORS(pixelcounterblue, resources={
    r"/count_pixel": {"origins": "*"},
    r"/counter": {"origins": "*"},
    r"/count": {"origins": "*"},
    r"/signups": {"origins": "*"},
    r"/api/createcounter": {"origins": "*"},
})


def _counter_document_id(name):
    """Create a stable Firestore ID so concurrent creates cannot duplicate a name."""
    normalized = str(name or '').strip().casefold().encode('utf-8')
    return f"counter-{hashlib.sha256(normalized).hexdigest()}"


def _get_accessible_counters():
    """Return counters visible to the current user without duplicate records."""
    user = get_user_data_from_token() or {}
    is_admin = user.get('role') == 'Administrator'
    counters = []
    seen_names = set()

    for doc in counter_ref.stream():
        data = doc.to_dict() or {}
        if not (is_admin or data.get('type') == 'global' or can_manage_resource(data)):
            continue
        normalized_name = str(data.get('name', '')).strip().casefold()
        if not normalized_name or normalized_name in seen_names:
            continue
        data['id'] = doc.id
        data['can_manage'] = can_manage_resource(data)
        for field in ('updated_at', 'last_count_at'):
            timestamp = data.get(field)
            data[f'{field}_display'] = (
                timestamp.strftime('%Y-%m-%d %H:%M UTC')
                if hasattr(timestamp, 'strftime') else '—'
            )
            data[f'{field}_sort'] = (
                timestamp.isoformat() if hasattr(timestamp, 'isoformat') else ''
            )
        counters.append(data)
        seen_names.add(normalized_name)

    return sorted(counters, key=lambda item: str(item.get('name', '')).casefold())


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
    disallowed_patterns = [
        d.to_dict().get('pattern') for d in disallowedorigion_ref.stream()
        if d.to_dict().get('pattern')
    ]

    # --- Step 1: Check API key override ---
    provided_api_key = request.headers.get('X-API-Key')
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
    """Check duplicate hash and validate counter BEFORE writing."""

    if not name:
        return "missing", "Missing counter name"

    # 1. Check if counter exists
    counter_docs = counter_ref.where('name', '==', name).limit(1).get()
    if not counter_docs:
        return "invalid_counter", f"Counter '{name}' does not exist"

    # If no email_hash provided, valid counter check is enough
    if not email_hash:
        return "ok", None

    if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', email_hash):
        return "invalid_hash", "email_hash must be a 16-128 character encoded hash"

    # 2. Check if (name + email_hash) already registered
    hash_id = hashlib.sha256(f'{name.casefold()}:{email_hash}'.encode('utf-8')).hexdigest()
    try:
        emailhash_ref.document(hash_id).create({
            "name": name,
            "email_hash": email_hash,
            "created_at": datetime.utcnow()
        })
    except AlreadyExists:
        return "duplicate", "Counter + Email_Hash already counted"

    return "ok", None


def increment_counter(name, amount=1):
    counter_docs = counter_ref.where('name', '==', name).limit(1).get()
    if not counter_docs:
        return False

    counter_doc = counter_docs[0]

    # totals_docs = counter_ref.where('name', '==', 'totals').limit(1).get()
    # totals_doc = totals_docs[0] if totals_docs else None

    counter_ref.document(counter_doc.id).update({
        'count': Increment(amount),
        'last_count_at': SERVER_TIMESTAMP,
    })

    # if totals_doc:
        # counter_ref.document(totals_doc.id).update({'count': Increment(1)})

    return True


def handle_count_request(is_pixel=False):
    try:
        remote_address, domain, path, referrer = get_request_context()

        allowed, reason = is_allowed_request(domain, remote_address, path)
        if not allowed:
            return jsonify({"error": reason}), 400

        name = request.args.get('id')
        amount = int(request.args.get('donation', 1))
        if amount < 1 or amount > 1_000_000:
            return jsonify({"error": "donation must be between 1 and 1000000"}), 422
        email_hash = request.args.get('email_hash')

        # --- email hash processing (duplicate + counter validation) ---
        status, msg = process_email_hash(name, email_hash)

        if status == "missing":
            return jsonify({"error": msg}), 400

        if status == "invalid_counter":
            return jsonify({"error": msg}), 404

        if status == "duplicate":
            return jsonify({"message": msg}), 200

        if status == "invalid_hash":
            return jsonify({"error": msg}), 422
        # else: status == "ok" → continue

        # --- Increment counter ---
        if not increment_counter(name, amount):
            return jsonify({"error": "Counter not found"}), 404

        if is_pixel:
            return send_file("static/images/onepixel.gif", mimetype="image/gif")

        return jsonify({"success": True}), 200

    except Exception as e:
        logging.exception("Error in count handler")
        return jsonify({"error": "Unable to process counter request"}), 500


@pixelcounterblue.route("/getsignups",
                        endpoint='getsignups')
@login_is_required
def getsignups():
    return redirect(url_for('pixelcounterblue.signup'))


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
        data = request.get_json(silent=True) or {}
        if not data.get('name'):
            return jsonify({'error': 'Counter name is required'}), 400
        if counter_ref.where('name', '==', data['name']).limit(1).get():
            return jsonify({'error': 'Counter ID already exists'}), 409
        user = get_user_data_from_token() or {}
        data['uuid'] = user.get('google_id')
        data['user'] = user.get('name')
        data['updated_at'] = SERVER_TIMESTAMP
        doc_ref = counter_ref.document(_counter_document_id(data['name']))
        doc_ref.create(data)
        log_activity('created', 'pixel counter', doc_ref.id, data.get('name'))
        return jsonify({"success": True}), 200
    except AlreadyExists:
        return jsonify({'error': 'Counter ID already exists'}), 409
    except Exception as e:
        return f"An Error Occured: {e}"


#
# API Route add with GET a counter by ID
# - requires json file body with id and count
#   /addset?id=<id>&count=<count>
#
@pixelcounterblue.route("/addset",
                        methods=['POST'],
                        endpoint='createset')
@login_is_required
def createset():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        counter_id = payload.get('id')
        if not counter_id:
            return jsonify({'error': 'Counter ID is required'}), 400
        name = payload.get('name') or counter_id
        if counter_ref.where('name', '==', name).limit(1).get():
            return jsonify({'error': 'Counter ID already exists'}), 409
        payload['updated_at'] = SERVER_TIMESTAMP
        doc_ref = counter_ref.document(_counter_document_id(name))
        doc_ref.create(payload)
        log_activity('created', 'pixel counter', doc_ref.id, name)
        return jsonify({"success": True}), 200
    except AlreadyExists:
        return jsonify({'error': 'Counter ID already exists'}), 409
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
    # Fetch active NROs for dropdown
    nro_stream = nro_ref.stream()
    nros = []
    for doc in nro_stream:
        d = doc.to_dict()
        if d.get("active", True):
            nros.append(d.get("name"))
    nros.sort()

    # Fetch users for assignment
    users_stream = users_ref.stream()
    users_list = []
    for doc in users_stream:
        u_data = doc.to_dict()
        u_id = u_data.get('uuid') or doc.id
        u_name = f"{u_data.get('given_name', '')} {u_data.get('last_name', u_data.get('family_name', ''))}".strip()
        if not u_name:
            u_name = u_data.get('email', 'Unknown User')
        users_list.append({'uuid': u_id, 'name': u_name})
    users_list.sort(key=lambda x: x['name'].lower())

    return render_template('listadd.html', nros=nros, users=users_list)



#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/documentation",
                        methods=['GET'],
                        endpoint='documentation')
@login_is_required
def documentation():
    snapshot = documentation_ref.document('main').get()
    stored = snapshot.to_dict() if snapshot.exists else {}
    title = stored.get('title') or DEFAULT_DOCUMENTATION_TITLE
    summary = stored.get('summary') or DEFAULT_DOCUMENTATION_SUMMARY
    content = stored.get('content') or DEFAULT_DOCUMENTATION_CONTENT
    return render_template('documentation.html', title=title, summary=summary,
                           sections=_documentation_sections(content))


@pixelcounterblue.route("/documentation/edit", methods=['GET', 'POST'],
                        endpoint='documentation_edit')
@login_is_required
@admin_required
def documentation_edit():
    doc_ref = documentation_ref.document('main')
    snapshot = doc_ref.get()
    stored = snapshot.to_dict() if snapshot.exists else {}

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        summary = request.form.get('summary', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('A title and documentation content are required')
        elif len(title) > 120 or len(summary) > 500 or len(content) > 50000:
            flash('The documentation exceeds the allowed length')
        else:
            doc_ref.set({
                'title': title, 'summary': summary, 'content': content,
                'updated_at': datetime.utcnow(),
                'updated_by': (get_user_data_from_token() or {}).get('email', 'Administrator'),
            })
            log_activity('updated', 'documentation', 'main', title)
            flash('Documentation updated successfully')
            return redirect(url_for('pixelcounterblue.documentation'))

    return render_template(
        'documentation_edit.html',
        title=stored.get('title') or DEFAULT_DOCUMENTATION_TITLE,
        summary=stored.get('summary') or DEFAULT_DOCUMENTATION_SUMMARY,
        content=stored.get('content') or DEFAULT_DOCUMENTATION_CONTENT,
    )


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

        decoded_data = get_user_data_from_token() or {}

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
                u'user': decoded_data.get('name'),
                u'assigned_users': request.form.getlist('assigned_users'),
                u'updated_at': SERVER_TIMESTAMP
            }

            doc_ref = counter_ref.document(_counter_document_id(data['name']))
            doc_ref.create(data)
            log_activity('created', 'pixel counter', doc_ref.id, data.get('name'))
            flash('Data Succesfully Submitted')
            return redirect(url_for('pixelcounterblue.read'))
    except AlreadyExists:
        flash('An Error Occured: The counter name has already been taken')
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
        # If ?id= passed → return single counter
        counter_id = request.args.get('id')
        if counter_id:
            doc = counter_ref.document(counter_id).get()
            data = require_resource_access(doc)
            return jsonify({"count": data.get("count", 0)}), 200

        return render_template('list.html', output=_get_accessible_counters())

    except Exception as e:
        return f"An Error Occurred: {e}"


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
        don = require_resource_access(counterlist)
        don["id"] = counterlist.id
        lists.append(don)
        
        # Fetch active NROs for dropdown
        nro_stream = nro_ref.stream()
        nros = []
        for doc in nro_stream:
            d = doc.to_dict()
            if d.get("active", True):
                nros.append(d.get("name"))
        nros.sort()

        # Fetch users for assignment
        users_stream = users_ref.stream()
        users_list = []
        for doc in users_stream:
            u_data = doc.to_dict()
            u_id = u_data.get('uuid') or doc.id
            u_name = f"{u_data.get('given_name', '')} {u_data.get('last_name', u_data.get('family_name', ''))}".strip()
            if not u_name:
                u_name = u_data.get('email', 'Unknown User')
            users_list.append({'uuid': u_id, 'name': u_name})
        users_list.sort(key=lambda x: x['name'].lower())

        return render_template('listedit.html', ngo=don, nros=nros, users=users_list)
    except Exception as e:
        return f"An Error Occured: {e}"



#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#
@pixelcounterblue.route("/listdelete",
                        methods=['POST', 'DELETE'])
@login_is_required
def listdelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        doc_ref = counter_ref.document(id)
        old_data = require_resource_access(doc_ref.get())
        doc_ref.delete()
        log_activity('deleted', 'pixel counter', id, old_data.get('name'))
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
        doc_ref = counter_ref.document(id)
        require_resource_access(doc_ref.get())
        allowed_fields = {'name', 'nro', 'url', 'count', 'contactpoint', 'campaign', 'type'}
        updates = {key: value for key, value in request.json.items() if key in allowed_fields}
        updates['updated_at'] = SERVER_TIMESTAMP
        doc_ref.update(updates)
        updated = doc_ref.get().to_dict() or {}
        log_activity('updated', 'pixel counter', id, updated.get('name'))
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

        id = request.form['id']
        doc_ref = counter_ref.document(id)
        old_data = require_resource_access(doc_ref.get())
        current_user = get_user_data_from_token() or {}

        data = {
            u'name': request.form.get('name'),
            u'nro': request.form.get('nro'),
            u'url': request.form.get('url'),
            u'count': int(request.form.get('count')),
            u'contactpoint': request.form.get('contactpoint'),
            u'campaign': request.form.get('campaign'),
            u'type': request.form.get('type'),
            u'uuid': old_data.get('uuid'),
            u'user': old_data.get('user'),
            u'assigned_users': (
                request.form.getlist('assigned_users')
                if current_user.get('role') == 'Administrator'
                else old_data.get('assigned_users', [])
            ),
            u'updated_at': SERVER_TIMESTAMP
        }
        doc_ref.update(data)
        log_activity('updated', 'pixel counter', id, data.get('name'))
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
@rate_limit(limit=300, window=60)
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
@rate_limit(limit=300, window=60)
def counter():
    return handle_count_request(is_pixel=False)


##
# The count route used for pixel image to increase a count using a GET request
# API endpoint /count?id=<id>
##
@pixelcounterblue.route("/count",
                        methods=['GET', 'POST',])
@cross_origin()
@rate_limit(limit=300, window=60)
def count():
    return handle_count_request(is_pixel=False)


##
# The API endpoint allows the user to get the endpoint total defined  by id
# API endpoint /signup?id=<id>
##
@pixelcounterblue.route("/signup",
                        methods=['GET', 'POST'],
                        endpoint='signup')
@login_is_required
def signup():
    counters = _get_accessible_counters()
    selected_name = ''
    result = None
    error = None

    if request.method == 'POST':
        selected_name = request.form.get('name', '').strip()
        if not selected_name:
            error = 'Please select a counter.'
        else:
            selected = next(
                (counter for counter in counters if counter.get('name') == selected_name),
                None,
            )
            if selected is None:
                error = 'That counter does not exist or you do not have access to it.'
            else:
                result = selected

    return render_template(
        'signups.html',
        counters=counters,
        selected_name=selected_name,
        result=result,
        error=error,
    )


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
@admin_required
def allowedlistadd():
    return render_template('allowedlistadd.html', **locals())


#
# API Route list all or a speific counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/allowedlist",
                        methods=['GET'],
                        endpoint='allowedlist')
@login_is_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
                        methods=['POST', 'DELETE'],
                        endpoint='allowedlistdelete')
@login_is_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def disallowedlistcreate():
    try:
        decoded_data = get_user_data_from_token() or {}

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
@admin_required
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
@admin_required
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
                        methods=['POST', 'DELETE'],
                        endpoint='disallowedlistdelete')
@login_is_required
@admin_required
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
                        methods=['POST', 'DELETE'])
@login_is_required
def delete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        doc_ref = counter_ref.document(id)
        old_data = require_resource_access(doc_ref.get())
        doc_ref.delete()
        log_activity('deleted', 'pixel counter', id, old_data.get('name'))
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

    # --- 3. Check if a counter with this name already exists ---
    # Counter documents use generated Firestore IDs, so uniqueness must be
    # checked against the stored name field rather than the document ID.
    existing = (
        counter_ref
        .where("name", "==", counter_name)
        .limit(1)
        .get()
    )
    if existing:
        return jsonify({"error": "Counter ID already exists"}), 409

    # --- 4. Create counter ---
    try:
        record = {
            "campaign": data.get("campaign", ""),
            "contactpoint": data.get("contactpoint", ""),
            "count": data.get("count", 0),
            "name": counter_name,
            "nro": data.get("nro", ""),
            "type": data.get("type", "global"),
            "url": data.get("url", ""),
            "user": data.get("user", ""),
            "uuid": data.get("uuid", ""),
            "updated_at": SERVER_TIMESTAMP
        }
        doc_ref = counter_ref.document(_counter_document_id(counter_name))
        doc_ref.create(record)
        log_activity(
            'created',
            'pixel counter',
            doc_ref.id,
            counter_name,
            user=getattr(g, 'api_key_owner', 'API user'),
        )
        return jsonify({
            "message": "Counter created successfully",
            "counter_name": counter_name
        }), 201
    except AlreadyExists:
        return jsonify({"error": "Counter ID already exists"}), 409
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500
