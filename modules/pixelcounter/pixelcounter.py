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
# Install Google Libraries
from google.cloud.firestore import Increment

# Journalist firestore collection
from system.firstoredb import counter_ref
from system.firstoredb import allowedorigion_ref
from system.firstoredb import disallowedorigion_ref
from system.firstoredb import emailhash_ref
from system.utils import resolve_ip_from_domain
from modules.auth.auth import login_is_required
# Import logging
import logging
import jwt
from urllib.parse import urlparse

pixelcounterblue = Blueprint('pixelcounterblue',
                             __name__, template_folder='templates')

CORS(pixelcounterblue)

@pixelcounterblue.route("/getsignups", endpoint='getsignups')
@login_is_required
def getsignups():
    return render_template('signups.html', **locals())


@pixelcounterblue.route("/get_my_ip", methods=["GET"])
def get_my_ip():
    return jsonify({'ip': request.remote_addr}), 200

#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/add", methods=['POST'], endpoint='create')
@login_is_required
def create():
    try:
        id = request.json['id']
        counter_ref.document(id).set(request.json)
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route add with GET a counter by ID - requires json file body with id and count
#   /addset?id=<id>&count=<count>
#
@pixelcounterblue.route("/addset", methods=['GET'], endpoint='createset')
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
@pixelcounterblue.route("/addlist", methods=['GET'], endpoint='addlist')
@login_is_required
def addlist():
    return render_template('listadd.html', **locals())
 
#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/documentation", methods=['GET'],
                        endpoint='documentation')
@login_is_required
def documentation():
    return render_template('documentation.html', **locals())
 
#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/testincrementiframe", methods=['GET'],
                        endpoint='testincrementiframe')
@login_is_required
def testincrementiframe():
    return render_template('test-display-iframe.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/testincrementimage", methods=['GET'],
                        endpoint='testincrementimage')
@login_is_required
def testincrementimage():
    return render_template('test-increment-image.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/testincrementscript", methods=['GET'],
                        endpoint='testincrementscript')
@login_is_required
def testincrementscript():
    return render_template('test-increment-script.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/testodometer", methods=['GET'],
                        endpoint='testodometer')
@login_is_required
def testodometer():
    return render_template('test-odometer.html', **locals())

#
# API Route add a counter by ID - requires json file body with id and count
#
@pixelcounterblue.route("/createlist", methods=['POST'],
                        endpoint='createlist')
@login_is_required
def createlist():
    try:

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

        id = request.form.get('id')

        # Check if id already exixst # check if short exist 
        docshort = counter_ref.where('id', '==', request.form.get('id')).get()
        if (len(list(docshort))):
            flash(f'An Error Occured: The counter name has already been taken')
            return redirect(url_for('pixelcounterblue.read'))            
        else:
            data = {
                u'id': request.form.get('id'),
                u'nro': request.form.get('nro'),
                u'url': request.form.get('url'),
                u'count': int(request.form.get('count')),
                u'contactpoint': request.form.get('contactpoint'),
                u'campaign': request.form.get('campaign'),
                u'type': request.form.get('type'),
                u'uuid': decoded_data.get('google_id'),
                u'user': decoded_data.get('name')
            }

            counter_ref.document(id).set(data)
            flash('Data Succesfully Submitted')
            return redirect(url_for('pixelcounterblue.read'))
    except Exception as e:
        flash('An Error Occvured', {e})
        return redirect(url_for('pixelcounterblue.addlist'))
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/list", methods=['GET'], endpoint='read')
@login_is_required
def read():
    try:

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

        # Check if ID was passed to URL query
        id = request.args.get('id')    
        if id:
            counter = counter_ref.document(id).get()
            return jsonify(u'{}'.format(counter.to_dict()['count'])), 200
        else:
            all_counters = []

            for doc in counter_ref.where("uuid", "==", decoded_data.get('google_id')).where('type', '==', 'local').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                all_counters.append(don)

            for doc in counter_ref.where('type', '==', 'global').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                all_counters.append(don)

            return render_template('list.html', output=all_counters)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/listedit", methods=['GET'], endpoint='listedit')
@login_is_required
def listedit():
    try:
        # Check if ID was passed to URL query
        counter_id = request.args.get('id')
        counter = counter_ref.document(counter_id).get()
        return render_template('listedit.html', ngo=counter.to_dict())
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/listdelete", methods=['GET', 'DELETE'])
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


@pixelcounterblue.route("/update", methods=['POST', 'PUT'])
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


@pixelcounterblue.route("/updateform", methods=['POST', 'PUT'], endpoint='updateform')
@login_is_required
def updateform():
    try:

        jwt_token = session.get('jwt_token')
        decoded_data = jwt.decode(jwt_token, 'secret_key', algorithms=['HS256'])

        id = request.form['id']

        data = {
            u'id': request.form.get('id'),
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

@pixelcounterblue.route('/count_pixel', methods=['GET','POST',])
@cross_origin()
def count_pixel():
    try:
        # Check if Remote Host is in the allowed list        
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict()['domain'])

        remote_address = None

        # Check if HTTP_X_FORWARDED_FOR is set
        if 'HTTP_X_FORWARDED_FOR' in request.environ:
            forwarded_for = request.environ['HTTP_X_FORWARDED_FOR']
            if forwarded_for in allowed_origin_list:
                remote_address = forwarded_for

        # If HTTP_X_FORWARDED_FOR is not set or not allowed, use REMOTE_ADDR
        if remote_address is None and 'REMOTE_ADDR' in request.environ:
            remote_address = request.environ['REMOTE_ADDR']

        # Now remote_address contains the appropriate remote address

        if remote_address is not None:
            # On allowed lsut, check if ID was passed to URL query
            email_hash = request.args.get('email_hash')            
            if email_hash is not None:
                docRef = emailhash_ref.where('email_hash', '==', email_hash).get()
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
            id = request.args.get('id')  
            counter_ref.document(id).update({u'count': Increment(1)})
            counter_ref.document('totals').update({u'count': Increment(1)})
            filename = 'static/images/onepixel.gif'
            return send_file(filename, mimetype='image/gif')
        # Add a default response if none of the conditions are met
        logging.info("No Match Allowed Lists")
        return f"Not in allowed list", 400
    except Exception as e:
        return f"An Error Occured: {e}", 500

#
# API Route Increase Counter by ID - requires json file body with id and count
# API endpoint /counter 
# json {"id":"GP Canada","count", 0}
#
@pixelcounterblue.route("/counter", methods=['POST', 'PUT'])
@cross_origin()
def counter():
    try:
        # Check if Remote Host is in the allowed list        
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict()['domain'])

        remote_address = None

        # Check if HTTP_X_FORWARDED_FOR is set
        if 'HTTP_X_FORWARDED_FOR' in request.environ:
            forwarded_for = request.environ['HTTP_X_FORWARDED_FOR']
            if forwarded_for in allowed_origin_list:
                remote_address = forwarded_for

        # If HTTP_X_FORWARDED_FOR is not set or not allowed, use REMOTE_ADDR
        if remote_address is None and 'REMOTE_ADDR' in request.environ:
            remote_address = request.environ['REMOTE_ADDR']

        # Now remote_address contains the appropriate remote address

        if remote_address is not None:
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
            id = request.args.get('id')  
            counter_ref.document(id).update({u'count': Increment(1)})
            counter_ref.document('totals').update({u'count': Increment(1)})    
            return jsonify({"success": True}), 200
        logging.info("No Match Allowed Lists")
        return f"Not in allowed list", 400

    except Exception as e:
        return f"An Error Occured: {e}", 500

##
# The count route used for pixel image to increase a count using a GET request
# API endpoint /count?id=<id>
##


@pixelcounterblue.route("/countdonation", methods=['GET', 'POST',])
@cross_origin()
def countdonation():
    try:
        # Check if Remote Host is in the allowed list        
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict()['domain'])
        try:

            remote_address = None

            # Check if HTTP_X_FORWARDED_FOR is set
            if 'HTTP_X_FORWARDED_FOR' in request.environ:
                forwarded_for = request.environ['HTTP_X_FORWARDED_FOR']
                if forwarded_for in allowed_origin_list:
                    remote_address = forwarded_for

            # If HTTP_X_FORWARDED_FOR is not set or not allowed, use REMOTE_ADDR
            if remote_address is None and 'REMOTE_ADDR' in request.environ:
                remote_address = request.environ['REMOTE_ADDR']

            # Now remote_address contains the appropriate remote address
            if remote_address is not None:
                # On allowed lsut, check if ID was passed to URL query
                amount = request.args.get('donation')
                if amount is not None:
                    # Add Counter
                    id = request.args.get('id')
                    amount_int = int(amount)
                    counter_ref.document(id).update({u'count': Increment(amount_int)})
                    counter_ref.document('totals').update({u'count': Increment(1)})
                else:
                    # Add Counter
                    id = request.args.get('id')  
                    counter_ref.document(id).update({u'count': Increment(1)})
                    counter_ref.document('totals').update({u'count': Increment(1)})
                logging.info("Counter Been Updated")
                return base64.b64decode(b'='), 200
            # Add a default response if none of the conditions are met
            logging.info("No Match Allowed Lists")
            return f"Not in allowed list", 400
        except Exception as e:
            return f"An Error Occured: {e}", 500
    except Exception as e:
        return f"An Error Occured: {e}", 500

##
# The count route used for pixel image to increase a count using a GET request
# API endpoint /count?id=<id>
##


@pixelcounterblue.route("/count", methods=['GET', 'POST',])
@cross_origin()
def count():
    try:
        # Check if Remote Host is in the allowed list        
        allowed_origin_list = []
        for doc in allowedorigion_ref.stream():
            allowed_origin_list.append(doc.to_dict())

        # check if the allowed url matches a pattern in disallowed list
        disallowed_origin_list = []
        for disdoc in disallowedorigion_ref.stream():
            disallowed_origin_list.append(disdoc.to_dict())

        # Define disallowed patterns
        disallowed_patterns = ['/wp-admin/', '/admin/', '/edit/']  

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

            # Get the domain from the 'Host' header
            request_domain = request.headers.get('Host')

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
            logging.info(f"Headers: {request.headers}")
            logging.info(f"Remote Address: {remote_address}")
            logging.info(f"Referrer URL: {referrer_url}")
            logging.info(f"Full Referrer URI: {full_referrer_uri}")
            logging.info(f"Referrer IP: {referrer_ip}")
            logging.info(f"Request Path: {request.path}")

            # Now remote_address contains the appropriate remote address
            if remote_address is not None:
                # Get the domain from the 'Host' header
                request_domain = request.headers.get('Host').split(':')[0]
                request_path = request.path
                # On allowed lsut, check if ID was passed to URL query
                # Check if the request domain matches any domain in the allowed list
                for allowed_origin in allowed_origin_list:
                    if ('domain' in allowed_origin and request_domain == allowed_origin['domain']) or \
                            ('ipaddress' in allowed_origin and remote_address == allowed_origin['ipaddress']):
                        # Check if the request path matches any disallowed patterns
                        for pattern in disallowed_patterns:
                            if pattern in request_path:
                                # Log and reject the request
                                logging.info("Disallowed URL accessed")
                                return "Disallowed URL", 403
                        # On allowed list, check if ID was passed to URL query                
                        email_hash = request.args.get('email_hash')
                        if email_hash is not None:
                            docRef = emailhash_ref.where('email_hash', '==', email_hash).get()
                            documents = [d for d in docRef]
                            # Check if hash value already exixsts in the database
                            if len(documents):
                                # If exists, don not increase count by 1
                                logging.info("Email hash Exist")
                                return '', 200
                            else:
                                # Add hashed email to database
                                data = {
                                    u'email_hash': email_hash,
                                }
                                emailhash_ref.document().set(data)
                        # Add Counter
                        id = request.args.get('id')
                        amount = request.args.get('donation')
                        if amount is not None:
                            # Convert amount to integer
                            amount_int = int(amount)
                            counter_ref.document(id).update({u'count': Increment(amount_int)})
                            counter_ref.document('totals').update({u'count': Increment(1)})                    
                        else:
                            counter_ref.document(id).update({u'count': Increment(1)})
                            counter_ref.document('totals').update({u'count': Increment(1)})
                        logging.info("Counter Been Updated")
                        return base64.b64decode(b'='), 200

            # Add a default response if none of the conditions are met
            logging.info("No Match Allowed Lists")
            return "Not in allowed list", 400
        except Exception as e:
            logging.error("Error: []" + e)
            return f"An Error Occured: {e}", 500
    except Exception as e:
        logging.error("No Match Allowed Lists []" + e)
        return f"Error no access firestore: {e}", 500

##
# The API endpoint allows the user to get the endpoint total defined  by id
# API endpoint /signup?id=<id>
##


@pixelcounterblue.route("/signup", methods=['POST', 'PUT'], endpoint='signup')
@login_is_required
def signup():    
    try:
        if request.method == "POST":
            id = request.form['id']
            counter = counter_ref.document(id).get()
            output = f"{ counter.to_dict()['count'] }"          
            return render_template('signups.html', output=output)
        return render_template('signups.html', output="No NRO name has been given")
    except Exception as e:
        return render_template('signups.html', output="An Error Occured: {}" + e)

##
# The API endpoint allows the user to get the endpoint total defined  by id
# API endpoint /signup?id=<id>
##


@pixelcounterblue.route("/signups", methods=['POST','GET'], endpoint='signups')
@cross_origin()
def signups():
    try:
        id = request.args.get('id')
        counter = counter_ref.document(id).get()
        output = counter.to_dict()['count']
        return jsonify({"unique_count": output, "id": id}), 200
    except Exception as e:
        return f"An Error Occured: {e}", 500

#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlistadd", methods=['GET'],
                        endpoint='allowedlistadd')
@login_is_required
def allowedlistadd():
    return render_template('allowedlistadd.html', **locals())
 
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlist", methods=['GET'],
                        endpoint='allowedlist')
@login_is_required
def allowedlist():
    try:
        allowedlist = []     
        for doc in allowedorigion_ref.stream():
            don = doc.to_dict()
            don["docid"] = doc.id
            allowedlist.append(don)

        return render_template('allowedlist.html', allowed=allowedlist)
    except Exception as e:
        return f"An Error Occured: {e}"
    
#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlistcreate", methods=['POST'],
                        endpoint='allowedlistcreate')
@login_is_required
def allowedlistcreate():
    try:
        id = request.form.get('id')        
        data = {
            u'id': request.form.get('id'),
            u'domain': request.form.get('domain'),
            u'ipaddress': request.form.get('ipaddress')
        }

        allowedorigion_ref.document(id).set(data)
        flash('Data Succesfully Submitted')
        return redirect(url_for('pixelcounterblue.allowedlist'))
    except Exception as e:
        flash('An Error Occvured')
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@pixelcounterblue.route("/allowedlistupdate", methods=['POST', 'PUT'],
                        endpoint='allowedlistupdate')
@login_is_required
def allowedlistupdate():
    try:
        id = request.form['id']
        data = {
            u'id': request.form.get('id'),
            u'domain': request.form.get('domain'),
            u'ipaddress': request.form.get('ipaddress')
        }
        allowedorigion_ref.document(id).update(data)
        return redirect(url_for('pixelcounterblue.allowedlist'))
    except Exception as e:
        return f"An Error Occured: {e}"    
    
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/allowedlistedit", methods=['GET'],
                        endpoint='allowedlistedit')
@login_is_required
def allowedlistedit():
    try:
        allowedlists = []
        # Check if ID was passed to URL query
        id = request.args.get('id')
        allowedlist = allowedorigion_ref.document(id).get()
        don = allowedlist.to_dict()
        don["docid"] = allowedlist.id
        allowedlists.append(don)

        return render_template('allowedlistedit.html', ngo=don)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/allowedlistdelete", methods=['GET', 'DELETE'],
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


@pixelcounterblue.route("/disallowedlistadd", methods=['GET'],
                        endpoint='disallowedlistadd')
@login_is_required
def disallowedlistadd():
    return render_template('disallowedlistadd.html', **locals())
 
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlist", methods=['GET'],
                        endpoint='disallowedlist')
@login_is_required
def disallowedlist():
    try:
        disallowedlist = []     
        for doc in disallowedorigion_ref.stream():
            don = doc.to_dict()
            don["docid"] = doc.id
            disallowedlist.append(don)

        return render_template('disallowedlist.html', allowed=disallowedlist)
    except Exception as e:
        return f"An Error Occured: {e}"
    
#
# API Route add a counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlistcreate", methods=['POST'],
                        endpoint='disallowedlistcreate')
@login_is_required
def disallowedlistcreate():
    try:
        id = request.form.get('id')        
        data = {
            u'id': request.form.get('id'),
            u'domain': request.form.get('domain')
        }
        
        disallowedorigion_ref.document(id).set(data)
        flash('Data Succesfully Submitted')
        return redirect(url_for('pixelcounterblue.disallowedlist'))
    except Exception as e:
        flash('An Error Occvured')
        return f"An Error Occured: {e}"

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@pixelcounterblue.route("/disallowedlistupdate", methods=['POST', 'PUT'],
                        endpoint='disallowedlistupdate')
@login_is_required
def disallowedlistupdate():
    try:
        id = request.form['id']
        data = {
            u'id': request.form.get('id'),
            u'domain': request.form.get('domain')
        }
        disallowedorigion_ref.document(id).update(data)
        return redirect(url_for('pixelcounterblue.disallowedlist'))
    except Exception as e:
        return f"An Error Occured: {e}"    
    
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@pixelcounterblue.route("/disallowedlistedit", methods=['GET'],
                        endpoint='disallowedlistedit')
@login_is_required
def disallowedlistedit():
    try:
        disallowedlists = []
        # Check if ID was passed to URL query
        id = request.args.get('id')
        disallowedlist = disallowedorigion_ref.document(id).get()
        don = disallowedlist.to_dict()
        don["docid"] = disallowedlist.id
        disallowedlists.append(don)

        return render_template('disallowedlistedit.html', ngo=don)
    except Exception as e:
        return f"An Error Occured: {e}"

#
# API Route Delete a counter by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@pixelcounterblue.route("/disallowedlistdelete", methods=['GET', 'DELETE'],
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


@pixelcounterblue.route("/delete", methods=['GET', 'DELETE'])
def delete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        counter_ref.document(id).delete()
        return jsonify({"success": True}), 200
    except Exception as e:
        return f"An Error Occured: {e}"
