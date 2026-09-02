# Get the Flask Files Required
from flask import (
    Blueprint,
    request,
    url_for,
    redirect,
    render_template
)
import logging

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

@frontpageblue.route("/contactus")
def contactus():
    return render_template('contactus.html', **locals())


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
