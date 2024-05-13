# Get the Flask Files Required
from flask import Blueprint, render_template

# Fake News firestore collection

from modules.auth.auth import login_is_required

# Set Blueprint’s name https://realpython.com/flask-blueprint/
dashboardblue = Blueprint('dashboardblue', __name__, 
                          template_folder='templates')


# Main page dashboard


@dashboardblue.route("/main", endpoint='main')
@login_is_required
def main():
    return render_template('dashboard.html', **locals())
