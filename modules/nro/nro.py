from flask import Blueprint, render_template, request, redirect, flash, url_for, g, jsonify
from system.firstoredb import nro_ref
from modules.auth.auth import login_is_required, admin_required
import datetime

nroblue = Blueprint("nroblue", __name__, template_folder="templates")

@nroblue.route("/nros", methods=["GET"])
@login_is_required
@admin_required
def nro_list():
    try:
        nros_stream = nro_ref.stream()
        nros = []
        for doc in nros_stream:
            data = doc.to_dict()
            data["id"] = doc.id
            nros.append(data)
        
        # Sort by name
        nros.sort(key=lambda x: x.get("name", "").lower())
        
        return render_template("nro_list.html", nros=nros, nonce=g.nonce)
    except Exception as e:
        flash(f"Error fetching NROs: {e}")
        return redirect(url_for("dashboardblue.main"))

@nroblue.route("/nros/add", methods=["GET", "POST"])
@login_is_required
@admin_required
def nro_add():
    if request.method == "POST":
        name = request.form.get("name")
        active = request.form.get("active") == "on"
        
        if not name:
            flash("Name is required")
            return redirect(url_for("nroblue.nro_add"))
            
        try:
            nro_ref.document().set({
                "name": name,
                "active": active,
                "created_at": datetime.datetime.utcnow()
            })
            flash("NRO created successfully")
            return redirect(url_for("nroblue.nro_list"))
        except Exception as e:
            flash(f"Error creating NRO: {e}")
            
    return render_template("nro_form.html", nro=None, nonce=g.nonce)

@nroblue.route("/nros/edit/<nro_id>", methods=["GET", "POST"])
@login_is_required
@admin_required
def nro_edit(nro_id):
    try:
        doc = nro_ref.document(nro_id).get()
        if not doc.exists:
            flash("NRO not found")
            return redirect(url_for("nroblue.nro_list"))
            
        nro = doc.to_dict()
        nro["id"] = doc.id
        
        if request.method == "POST":
            name = request.form.get("name")
            active = request.form.get("active") == "on"
            
            if not name:
                flash("Name is required")
                return redirect(url_for("nroblue.nro_edit", nro_id=nro_id))
                
            nro_ref.document(nro_id).update({
                "name": name,
                "active": active,
                "updated_at": datetime.datetime.utcnow()
            })
            flash("NRO updated successfully")
            return redirect(url_for("nroblue.nro_list"))
            
        return render_template("nro_form.html", nro=nro, nonce=g.nonce)
    except Exception as e:
        flash(f"Error updating NRO: {e}")
        return redirect(url_for("nroblue.nro_list"))

@nroblue.route("/nros/delete/<nro_id>", methods=["POST"])
@login_is_required
@admin_required
def nro_delete(nro_id):
    try:
        nro_ref.document(nro_id).delete()
        flash("NRO deleted successfully")
    except Exception as e:
        flash(f"Error deleting NRO: {e}")
    return redirect(url_for("nroblue.nro_list"))

@nroblue.route("/nros/toggle/<nro_id>", methods=["POST"])
@login_is_required
@admin_required
def nro_toggle(nro_id):
    try:
        data = request.get_json()
        active = data.get("active")
        
        nro_ref.document(nro_id).update({
            "active": active,
            "updated_at": datetime.datetime.utcnow()
        })
        return jsonify({"success": True, "message": "Status updated"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
