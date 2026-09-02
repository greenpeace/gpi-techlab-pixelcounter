# Get the Flask Files Required
from flask import Blueprint, render_template, session, url_for

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
    # Retrieve top 5 counters by their stored count value.
    top_counters_query = counter_ref.order_by(
        u'count', direction=firestore.Query.DESCENDING
    )
    top_counters = []
    seen_counter_names = set()

    # Older duplicate records can still exist in Firestore. Because the query
    # is ordered by count, keeping the first document for each name displays
    # the highest value without adding duplicate records together.
    for doc in top_counters_query.stream():
        data = doc.to_dict()
        name = data.get('name', doc.id)
        normalized_name = str(name).casefold()

        if normalized_name in seen_counter_names:
            continue

        value = data.get('count', 0)
        formatted_value = f"{value:,}" if isinstance(value, (int, float)) else str(value)
        top_counters.append({
            "name": name,
            "value": value,
            "formatted_value": formatted_value,
        })
        seen_counter_names.add(normalized_name)

        if len(top_counters) == 5:
            break

    # Recent system activities (limit 5)
    recent_activities = (
        activity_ref.order_by(u'timestamp', direction=firestore.Query.DESCENDING)
        .limit(5)
        .stream()
    )
    activities = []
    for doc in recent_activities:
        activity = doc.to_dict()
        timestamp = activity.get('timestamp')
        activity['display_timestamp'] = (
            timestamp.strftime('%Y-%m-%d %H:%M UTC')
            if hasattr(timestamp, 'strftime')
            else str(timestamp or '')
        )
        activities.append(activity)

    # Quick links configuration
    quick_links = [
        {"label": "Pixel Counter", "url": url_for('pixelcounterblue.read'), "icon": "ti-paint-roller"},
        {"label": "QR Code", "url": url_for('qrcodeblue.qrcode'), "icon": "ti-qr"},
        {"label": "URL Shortener", "url": url_for('urlshortnerblue.urlshortner'), "icon": "ti-link"},
        {"label": "API Keys", "url": url_for('apikeyblue.apikey_list'), "icon": "ti-key"},
    ]

    if session.get('role') == 'Administrator':
        quick_links.append({
            "label": "NRO",
            "url": url_for('nroblue.nro_list'),
            "icon": "ti-settings",
        })

    return render_template(
        "dashboard.html",
        top_counters=top_counters,
        activities=activities,
        quick_links=quick_links,
    )
