from flask import (
    Blueprint,
    request,
    session,
    jsonify,
    url_for,
    redirect,
    render_template,
    flash,
    abort,
    current_app
)

# Install Google Libraries
from google.cloud.firestore import Increment

from modules.auth.auth import login_is_required
# Import project id
from system.setenv import project_id
from system.getsecret import getsecrets

# Journalist firestore collection
from system.firstoredb import molnurl_ref
from system.date import datenow
from system.activity import log_activity
from system.authorization import can_manage_resource, require_resource_access
from system.url_safety import fetch_public_html
from system.jwt_utils import decode_jwt_token

# to get meta details from an url
from bs4 import BeautifulSoup
from werkzeug.exceptions import HTTPException
import base64
import re

# Get Logging
import logging

# Get BigQuery
import system.bigquery

urlshortnerblue = Blueprint('urlshortnerblue',
                            __name__,
                            template_folder='templates')


def is_reserved_short_name(short_name):
    """Return whether a short name is already occupied by a fixed app route."""
    candidate = f"/{short_name.strip('/')}"
    return any(
        rule.rule == candidate and rule.endpoint != 'urlshortnerblue.urlredirect'
        for rule in current_app.url_map.iter_rules()
    )


# Get the secret for dataset


dataset_id = getsecrets("urlshortner_stats_dataset_id", project_id)

# Get the secret for table


table_id = getsecrets("urlshortner_stats_table_id", project_id)


#
# API Route add a searchlink by ID - requires json file body with id and count
#


@urlshortnerblue.route("/urlshortneradd",
                       methods=['GET'],
                       endpoint='urlshortneradd')
@login_is_required
def urlshortneradd():
    return render_template('urlshortneradd.html', **locals())

#
# API Route add a searchlink by ID - requires json file body with id and count
#


@urlshortnerblue.route("/urlshortnercreate",
                       methods=['POST'],
                       endpoint='urlshortnercreate')
@login_is_required
def urlshortnercreate():
    try:
        # Get the URL from the form and make a request to get data from it
        url = request.form.get('url')
        title = ""
        description = ""
        try:
            # Request URL and get meta data
            soup = BeautifulSoup(fetch_public_html(url), 'html.parser')
            # Find the title and description from the URL of the redirect
            title = soup.find("meta",  property="og:title")
            description = soup.find("meta",  property="og:description")
            # meta_tag = soup.find('meta', attrs={'name': 'description'})
        except ValueError as e:
            flash(str(e))
            return redirect(url_for('urlshortnerblue.urlshortner'))

        # generates id
        doc_ref = molnurl_ref.document()
        id = doc_ref.id

        # CHeck if system generate short name or user provided shortname
        if request.form.get('domain') != "":
            requested_short = request.form.get('domain', '').strip()
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', requested_short):
                flash('Short names may contain only letters, numbers, underscores, and hyphens')
                return redirect(url_for('urlshortnerblue.urlshortner'))
            if is_reserved_short_name(requested_short):
                flash('That short name is reserved by an application route')
                return redirect(url_for('urlshortnerblue.urlshortner'))
            # check if short exist
            docshort = molnurl_ref.where('short', '==', requested_short).limit(1).get()
            if (len(list(docshort))):
                flash('An Error Occured: The short link name is already in use')
                return redirect(url_for('urlshortnerblue.urlshortner'))
            else:
                short = requested_short
        else:
            message = id
            message_bytes = message.encode('ascii')
            base64_bytes = base64.urlsafe_b64encode(message_bytes)
            short = base64_bytes.decode('ascii')[:6]

        jwt_token = session.get('jwt_token')
        decoded_data = decode_jwt_token(jwt_token)

        data = {
            u'active': True,
            u'date': datenow(),
            u'meta_title': title["content"] if title else "No meta title given",
            u'meta_description': description["content"] if description else "No meta title given",
            u'domain': request.form.get('domain'),
            u'url': request.form.get('url'),
            u'language': request.form.get('language'),
            u'country': request.form.get('country'),
            u'click': 0,
            u'uniqueclick': 0,
            u'short': short,
            u'type': request.form.get('type'),
            u'uuid': decoded_data.get('google_id'),
            u'user': decoded_data.get('name')
        }

        molnurl_ref.document(id).set(data)
        log_activity('created', 'URL shortener', id, data.get('short'))
        flash('Data Succesfully Submitted')
        return redirect(url_for('urlshortnerblue.urlshortner'))
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('urlshortnerblue.urlshortner'))
#
# API Route list all or a speific counter by ID - requires json file body with id and count
#


@urlshortnerblue.route("/urlshortner",
                       methods=['GET'],
                       endpoint='urlshortner')
@login_is_required
def urlshortner():
    try:
        jwt_token = session.get('jwt_token')
        decoded_data = decode_jwt_token(jwt_token)

        # Check if ID was passed to URL query

        id = request.args.get('id')
        if id:
            urlshortnerlink = molnurl_ref.document(id).get()
            data = require_resource_access(urlshortnerlink)
            data['docid'] = urlshortnerlink.id
            return jsonify(data), 200
        else:
            all_urlshortnerlinks = []
            for doc in molnurl_ref.where("uuid",
                                         "==",
                                         decoded_data.get('google_id')).where('type', '==', 'local').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                don["can_manage"] = can_manage_resource(don)
                all_urlshortnerlinks.append(don)

            for doc in molnurl_ref.where('type', '==', 'global').stream():
                don = doc.to_dict()
                don["docid"] = doc.id
                if doc.id not in {item['docid'] for item in all_urlshortnerlinks}:
                    don["can_manage"] = can_manage_resource(don)
                    all_urlshortnerlinks.append(don)

            return render_template('urlshortner.html', output=all_urlshortnerlinks)
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('urlshortnerblue.urlshortner'))

#
# API Route list all or a speific searchlink by ID - requires json file body with id and count
#


@urlshortnerblue.route("/urlshortneredit",
                       methods=['GET'],
                       endpoint='urlshortneredit')
@login_is_required
def urlshortneredit():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        urlshortnerlink = molnurl_ref.document(id).get()
        ngo = require_resource_access(urlshortnerlink)
        return render_template('urlshortneredit.html', **locals())
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('urlshortnerblue.urlshortner'))

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@urlshortnerblue.route("/urlshortnerdelete",
                       methods=['POST', 'DELETE'],
                       endpoint='urlshortnerdelete')
@login_is_required
def urlshortnerdelete():
    try:
        # Check for ID in URL query
        id = request.args.get('id')
        doc_ref = molnurl_ref.document(id)
        old_data = require_resource_access(doc_ref.get())
        doc_ref.delete()
        log_activity('deleted', 'URL shortener', id, old_data.get('short'))
        return redirect(url_for('urlshortnerblue.urlshortner'))
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('urlshortnerblue.urlshortner'))

#
# API Route Delete a csearchlink by ID /delete?id=<id>
# API Enfpoint /delete?id=<id>
#


@urlshortnerblue.route("/urlshortneractive",
                       methods=['POST'],
                       endpoint='urlshortneractive')
@login_is_required
def urlshortneractive():
    try:
        # Check if ID was passed to URL query
        id = request.args.get('id')
        doc_ref = molnurl_ref.document(id)
        urlshortneractive = require_resource_access(doc_ref.get())

        # Update flag that translation done
        if urlshortneractive['active'] is True:
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
            'URL shortener',
            id,
            urlshortneractive.get('short'),
        )
        return redirect(url_for('urlshortnerblue.urlshortner'))
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('urlshortnerblue.urlshortner'))

#
# API Route Update a counter by ID - requires json file body with id and count
# API endpoint /update?id=<id>&count=<count>
#


@urlshortnerblue.route("/urlshortnerupdate",
                       methods=['POST', 'PUT'],
                       endpoint='urlshortnerupdate')
@login_is_required
def urlshortnerupdate():
    try:
        id = request.form['id']

        doc_ref = molnurl_ref.document(id)
        ngo = require_resource_access(doc_ref.get())

        # Get the URL from the form and make a request to get data from it
        url = request.form.get('url')
        title = None
        description = None
        try:
            soup = BeautifulSoup(fetch_public_html(url), 'html.parser')

            # Find the title and description from the URL of the redirect
            title = soup.find("meta",  property="og:title")
            description = soup.find("meta",  property="og:description")
        except ValueError as e:
            flash(str(e))
            return redirect(url_for('urlshortnerblue.urlshortneredit', id=id))

        # CHeck if system generate short name or user provided shortname
        if request.form.get('domain') != "":
            short = request.form.get('domain', '').strip()
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', short):
                flash('Short names may contain only letters, numbers, underscores, and hyphens')
                return redirect(url_for('urlshortnerblue.urlshortneredit', id=id))
            if is_reserved_short_name(short):
                flash('That short name is reserved by an application route')
                return redirect(url_for('urlshortnerblue.urlshortneredit', id=id))
            duplicate = molnurl_ref.where('short', '==', short).get()
            if any(doc.id != id for doc in duplicate):
                flash('The short link name is already in use')
                return redirect(url_for('urlshortnerblue.urlshortneredit', id=id))
        else:
            message = id
            message_bytes = message.encode('ascii')
            base64_bytes = base64.urlsafe_b64encode(message_bytes)
            short = base64_bytes.decode('ascii')[:6]

        jwt_token = session.get('jwt_token')
        decoded_data = decode_jwt_token(jwt_token)

        data = {
            u'active': True,
            u'date': ngo['date'] if ngo['date'] else datenow(),
            u'uid': ngo.get('uid') or ngo.get('uuid'),
            u'meta_title': ngo.get('meta_title') or (title.get('content') if title else 'No meta title given'),
            u'meta_description': ngo.get('meta_description') or (description.get('content') if description else 'No meta description given'),
            u'domain': request.form.get('domain'),
            u'url': request.form.get('url'),
            u'language': request.form.get('language'),
            u'country': request.form.get('country'),
            u'short': short,
            u'type': request.form.get('type'),
            u'uuid': ngo.get('uuid'),
            u'user': ngo.get('user')
        }

        doc_ref.update(data)
        log_activity('updated', 'URL shortener', id, data.get('short'))
        # Return to the list
        return redirect(url_for('urlshortnerblue.urlshortner'))
    except Exception as e:
        flash('An Error Occured: ' + str(e))
        return redirect(url_for('urlshortnerblue.urlshortner'))


@urlshortnerblue.route('/<id>',
                       methods=['POST', 'GET', 'PUT'],
                       endpoint='urlredirect')
def urlredirect(id):
    try:
        # short = request.host_url + id
        for doc in molnurl_ref.where(u'short', u'==', id).stream():
            link_data = doc.to_dict()
            if not link_data.get('active', False):
                abort(404)
            url = u'{}'.format(link_data['url'])
            # Add Counter
            molnurl_ref.document(doc.id).update({u'click': Increment(1)})
            # writetobigquery(doc)
            # Redirect
            print("Redirecting to: {}".format(url))
            return redirect(url, code=307)
        abort(404)
    except HTTPException:
        raise
    except Exception:
        logging.exception('Unable to resolve short URL')
        return redirect(url_for('frontpageblue.index'))


def writetobigquery(doc):
    # Create list for BigQuery save
    urlshortnerstats_bq = []

    # Create BQ json string
    urlshortnerstats_bq.append({
        'short': id if id else '',
        'date': datenow(),
        'docid': doc.id if doc.id else '',
        'host': request.host if request.host else '',
        'host_url': request.host_url if request.host_url else '',
        'ip_address': request.remote_addr if request.remote_addr else '',
        'requested_url': request.url if request.url else '',
        'referer_page': request.referrer if request.referrer else '',
        'schema': request.scheme if request.scheme else '',
        'routing_exception': request.routing_exception if request.routing_exception else '',
        'origin': request.origin if request.origin else '',
        'method': request.method if request.method else '',
        'full_path': request.full_path if request.full_path else '',
        'user_agent': request.headers.get('User-Agent') if request.headers.get('User-Agent') else '',
        'language': request.headers.get('Accept-Language') if request.headers.get('Accept-Language') else '',
        'user_agent_language': request.user_agent.language if request.user_agent.language else '',
        'browser': request.user_agent.browser if request.user_agent.browser else '',
        'platform': request.user_agent.platform if request.user_agent.platform else '',
        'version': request.user_agent.version if request.user_agent.version else '',
        'user_agent_string': request.user_agent.string if request.user_agent.string else '',
        'page_name': request.path if request.path else '',
        'query_string': request.query_string if request.query_string else ''
    })

    try:
        if system.bigquery.exist_dataset_table(table_id, dataset_id, project_id, system.bigquery.schema_shortnerstats):
            system.bigquery.insert_rows_bq(table_id, dataset_id, project_id, urlshortnerstats_bq)
        logging.info("Info: record written to BigQUery")
        # print('{{"Info: url: {} request response time in hh:mm:ss {} ."}}'.format(url,
        # time.strftime("%H:%M:%S", time.gmtime(time.time()))))
        # Slack Notification
        # payload = '{{"text":"Info: url: {} request response time in hh:mm:ss {} ."}}'.format(url,
        # time.strftime("%H:%M:%S", time.gmtime(time.time())))
    except Exception as e:
        logging.error("Error: Writing data to BigQuery" + e)
        return redirect(url_for('frontpageblue.index'))
