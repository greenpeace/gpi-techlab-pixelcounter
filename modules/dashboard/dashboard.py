# Get the Flask Files Required
from flask import Blueprint, g, request, render_template
# Carbon tracking
#from codecarbon import track_emissions

# Set Blueprint’s name https://realpython.com/flask-blueprint/
dashboardblue = Blueprint('dashboardblue', __name__)

from modules.auth.auth import login_is_required

# Main page dashboard
@dashboardblue.route("/main", endpoint='main')
@login_is_required
#@track_emissions
def main():
    return render_template('dashboard.html', **locals())
