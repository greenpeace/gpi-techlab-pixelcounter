# Get the Flask Files Required
from flask import Blueprint, render_template, url_for

# Auth requirement
from modules.auth.auth import login_is_required

# Firestore references
from system.firstoredb import db, counter_ref, activity_ref
from firebase_admin import firestore

# Set Blueprint’s name

dashboardblue = Blueprint('dashboardblue', __name__, template_folder='templates')


@dashboardblue.route("/main", endpoint='main')
@login_is_required
def main():
    # Global counter (assuming a document named 'global' holds total count)
    # (Removed per user request)
    # Retrieve top 5 counters by value
    top_counters_query = (
        counter_ref.order_by(u'value', direction=firestore.Query.DESCENDING)
        .limit(5)
    )
    top_counters = [
        {"name": doc.id, "value": doc.to_dict().get('value', 0)}
        for doc in top_counters_query.stream()
    ]

    # Recent system activities (limit 5)
    recent_activities = (
        activity_ref.order_by(u'timestamp', direction=firestore.Query.DESCENDING)
        .limit(5)
        .stream()
    )
    activities = [doc.to_dict() for doc in recent_activities]

    # Quick links configuration
    quick_links = [
        {"label": "Pixel Counter", "url": url_for('pixelcounterblue.read'), "icon": "ti-paint-roller"},
        {"label": "QR Code", "url": url_for('qrcodeblue.qrcode'), "icon": "ti-qr"},
        {"label": "URL Shortener", "url": url_for('urlshortnerblue.urlshortner'), "icon": "ti-link"},
        {"label": "NRO", "url": url_for('nroblue.nro_list'), "icon": "ti-settings"},
        {"label": "API Keys", "url": url_for('apikeyblue.apikey_list'), "icon": "ti-key"},
    ]

    return render_template(
        "dashboard.html",
        top_counters=top_counters,
        activities=activities,
        quick_links=quick_links,
    )
