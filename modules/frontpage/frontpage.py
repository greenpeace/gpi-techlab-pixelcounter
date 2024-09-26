# Get the Flask Files Required
from flask import (
    Blueprint,
    request,
    url_for,
    redirect,
    render_template
)
import logging
# import system.visitors

# Fake News firestore collection
from system.firstoredb import crm_ref
# Set Blueprint’s name https://realpython.com/flask-blueprint/
frontpageblue = Blueprint('frontpageblue', __name__,
                          template_folder='templates')

# @frontpageblue.before_request
# def do_something_when_a_request_comes_in():
# system.visitors.track_visitor()

#
# API Route Default displays a webpage
#


@frontpageblue.route("/")
def index():
    return render_template('landing.html', **locals())

#
# About Us Page
#


@frontpageblue.route("/aboutus")
def aboutus():
    return render_template('aboutus.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/contactus")
def contactus():
    return render_template('contactus.html', **locals())


@frontpageblue.route("/contactform", methods=['POST'])
def contactform():
    try:
        # check if email already exist
        docsurl = crm_ref.where(u'email', u'==', request.form.get('email')).stream()
        if (len(list(docsurl))):
            logging.info("URL Exist, we will ignore")
        else:
            data = {
                u'active': True,
                u'firstname': request.form.get('firstname') if request.form.get('firstname') else '',
                u'lastname': request.form.get('lastname') if request.form.get('lastname') else '',
                u'email': request.form.get('email') if request.form.get('email') else '',
                u'phone': request.form.get('phone') if request.form.get('phone') else '',
                u'address': '',
                u'source': 'Contact Form',
                u'site': '',
                u'newsletter': False,
                u'subject': request.form.get('subject') if request.form.get('subject') else '',
                u'message': request.form.get('message') if request.form.get('message') else ''
            }

            crm_ref.document().set(data)
        return redirect(url_for('frontpageblue.index'))
    except Exception as e:
        print(e)
        return redirect(url_for('frontpageblue.index'))


@frontpageblue.route("/newsletter", methods=['POST'])
def newsletter():
    try:
        # duplicate check
        docsurl = crm_ref.where(u'email', u'==', request.form.get('email')).stream()
        if (len(list(docsurl))):
            logging.info("URL Exist, we will ignore")
        else:
            data = {
                u'active': True,
                u'firstname': request.form.get('firstname') if request.form.get('firstname') else '',
                u'lastname': request.form.get('lastname') if request.form.get('lastname') else '',
                u'email': request.form.get('email') if request.form.get('email') else '',
                u'phone': request.form.get('phone') if request.form.get('phone') else '',
                u'address': '',
                u'source': 'Newsletter',
                u'site': '',
                u'newsletter': False,
                u'subject': request.form.get('subject') if request.form.get('subject') else '',
                u'message': request.form.get('message') if request.form.get('message') else ''
            }

            crm_ref.document().set(data)
        return redirect(url_for('frontpageblue.index'))
    except Exception as e:
        print(e)
        return redirect(url_for('frontpageblue.index'))
#
# API Route Default displays a webpage
#


@frontpageblue.route("/blogsingle")
def blogsingle():
    return render_template('blogsingle.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/blogcard")
def blogcard():
    return render_template('blogcard.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/career")
def career():
    return render_template('career.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/privacypolicy")
def privacypolicy():
    return render_template('privacypolicy.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/termsandconditions")
def termsandconditions():
    return render_template('termsandconditions.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/faq")
def faq():
    return render_template('faq.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/techlab")
def techlab():
    return render_template('techlab.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/datalab")
def datalab():
    return render_template('datalab.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/sciencelab")
def sciencelab():
    return render_template('sciencelab.html', **locals())

#
# API Route Default displays a webpage
#


@frontpageblue.route("/medialab")
def medialab():
    return render_template('medialab.html', **locals())
