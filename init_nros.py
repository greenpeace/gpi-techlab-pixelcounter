import sys
import os

# Add the current directory to the path so we can import system
sys.path.append(os.getcwd())

try:
    from system.firstoredb import nro_ref
except ImportError:
    print("Could not import system.firstoredb. Make sure you are running this script from the project root.")
    sys.exit(1)

nro_list = [
    "GP Central & Eastern Europe",
    "GP European Unit",
    "GPI",
    "GP Czech Republic",
    "GP Belgium",
    "GP UK",
    "GP USA",
    "GP Mexico",
    "GP Mediterranean",
    "GP Italy",
    "GP Switzerland",
    "GP Australia / Pacific",
    "GP Canada",
    "GP Andino",
    "GP Southeast Asia",
    "GP East Asia",
    "GP Brasil",
    "GP Africa",
    "GP Germany",
    "GP Middle East & North Africa",
    "GP South Asia",
    "GP Aotearoa",
    "GP Nordic",
    "GP France-Luxembourg",
    "GP Netherlands",
    "GP Greece",
    "GP Research Laboratories",
    "GP Spain"
]

def init_nros():
    print("Checking NROs...")
    
    # Fetch existing to avoid duplicates
    existing_nros = [doc.to_dict().get("name") for doc in nro_ref.stream()]
    
    count = 0
    for nro_name in nro_list:
        if nro_name not in existing_nros:
            print(f"Adding NRO: {nro_name}")
            nro_ref.document().set({
                "name": nro_name,
                "active": True
            })
            count += 1
        else:
            print(f"Skipping existing: {nro_name}")
            
    print(f"Finished. Added {count} new NROs.")

if __name__ == "__main__":
    init_nros()
