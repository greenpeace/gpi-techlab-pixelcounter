import sys
import os

filepath = 'modules/pixelcounter/pixelcounter.py'

with open(filepath, 'r') as f:
    content = f.read()

# 1. Update imports
import_old = """from system.firstoredb import (
    emailhash_ref,
    counter_ref,
    allowedorigion_ref,
    disallowedorigion_ref,
    users_ref
)"""

import_new = """from system.firstoredb import (
    emailhash_ref,
    counter_ref,
    allowedorigion_ref,
    disallowedorigion_ref,
    users_ref,
    nro_ref
)"""

content = content.replace(import_old, import_new)

# 2. Update addlist to default to fetching NROs
addlist_old = """@pixelcounterblue.route("/addlist",
                        methods=['GET'],
                        endpoint='addlist')
@login_is_required
def addlist():
    return render_template('listadd.html', **locals())"""

addlist_new = """@pixelcounterblue.route("/addlist",
                        methods=['GET'],
                        endpoint='addlist')
@login_is_required
def addlist():
    # Fetch NROs
    nro_stream = nro_ref.stream()
    nros = []
    for doc in nro_stream:
        d = doc.to_dict()
        if d.get("active", True):
            nros.append(d.get("name"))
    nros.sort()
    
    return render_template('listadd.html', nros=nros, **locals())"""

content = content.replace(addlist_old, addlist_new)

# 3. Update listedit (function 'listedit' is typically mapped to /listedit route)
# Finding the block:
listedit_block_old = """        # Check if ID was passed to URL query
        id = request.args.get('id')
        counterlist = counter_ref.document(id).get()
        don = counterlist.to_dict()
        don["id"] = counterlist.id
        lists.append(don)

        return render_template('listedit.html', ngo=don)
    except Exception as e:
        return f"An Error Occured: {e}" """

listedit_block_new = """        # Check if ID was passed to URL query
        id = request.args.get('id')
        counterlist = counter_ref.document(id).get()
        don = counterlist.to_dict()
        don["id"] = counterlist.id
        lists.append(don)
        
        # Fetch NROs
        nro_stream = nro_ref.stream()
        nros = []
        for doc in nro_stream:
            d = doc.to_dict()
            if d.get("active", True):
                nros.append(d.get("name"))
        nros.sort()

        return render_template('listedit.html', ngo=don, nros=nros)
    except Exception as e:
        return f"An Error Occured: {e}" """

if listedit_block_old in content:
    content = content.replace(listedit_block_old, listedit_block_new)
else:
    print("Warning: listedit block not found exactly.")

with open(filepath, 'w') as f:
    f.write(content)

print("Updated pixelcounter.py for NROs.")
