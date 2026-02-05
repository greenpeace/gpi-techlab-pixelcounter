import sys
import os

filepath = 'modules/pixelcounter/pixelcounter.py'

with open(filepath, 'r') as f:
    content = f.read()

# 1. Add users_ref import
import_block_old = """from system.firstoredb import (
    emailhash_ref,
    counter_ref,
    allowedorigion_ref,
    disallowedorigion_ref
)"""

import_block_new = """from system.firstoredb import (
    emailhash_ref,
    counter_ref,
    allowedorigion_ref,
    disallowedorigion_ref,
    users_ref
)"""

content = content.replace(import_block_old, import_block_new)

# 2. Replace the read() logic
read_logic_old = """        # ---- ROLE LOGIC ----
        all_counters = []

        if user_role == "Administrator":
            # ADMIN → see ALL counters, local + global
            docs = counter_ref.stream()
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                all_counters.append(data)

        else:
            # NORMAL USER → local counters for user + global counters
            local_docs = counter_ref.where("uuid", "==", user_uuid)\\
                                    .where("type", "==", "local")\\
                                    .stream()
            for doc in local_docs:
                data = doc.to_dict()
                data["id"] = doc.id
                all_counters.append(data)

            global_docs = counter_ref.where("type", "==", "global").stream()
            for doc in global_docs:
                data = doc.to_dict()
                data["id"] = doc.id
                all_counters.append(data)

        return render_template('list.html', output=all_counters)

    except Exception as e:
        return f"An Error Occurred: {e}" """

read_logic_new = """        # ---- ROLE LOGIC ----
        all_counters = []
        seen_ids = set()

        if user_role == "Administrator":
            # ADMIN → see ALL counters
            docs = counter_ref.stream()
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                all_counters.append(data)
        else:
            # NORMAL USER:
            # 1. Fetch User Profile to get NRO
            user_doc = users_ref.document(user_uuid).get()
            if not user_doc.exists:
                user_nro = None
            else:
                user_data = user_doc.to_dict()
                user_nro = user_data.get('nro')

            # 2. Get Global Counters (everyone sees these)
            global_docs = counter_ref.where("type", "==", "global").stream()
            for doc in global_docs:
                if doc.id not in seen_ids:
                    data = doc.to_dict()
                    data["id"] = doc.id
                    all_counters.append(data)
                    seen_ids.add(doc.id)

            # 3. Get Owned Counters (uuid match)
            owned_docs = counter_ref.where("uuid", "==", user_uuid).stream()
            for doc in owned_docs:
                if doc.id not in seen_ids:
                    data = doc.to_dict()
                    data["id"] = doc.id
                    all_counters.append(data)
                    seen_ids.add(doc.id)

            # 4. Get NRO Local Counters
            if user_nro:
                nro_docs = counter_ref.where("nro", "==", user_nro).stream()
                for doc in nro_docs:
                    if doc.id not in seen_ids:
                        d = doc.to_dict()
                        if d.get('type') == 'local':
                            data = d
                            data["id"] = doc.id
                            all_counters.append(data)
                            seen_ids.add(doc.id)

        return render_template('list.html', output=all_counters)

    except Exception as e:
        return f"An Error Occurred: {e}" """

if read_logic_old not in content:
    print("Warning: old read logic block not found exactly. Contents might have changed.")

content = content.replace(read_logic_old, read_logic_new)

with open(filepath, 'w') as f:
    f.write(content)

print("Modules updated.")
