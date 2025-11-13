import threading
import time
import requests
import ipaddress
from flask import Flask, request, jsonify
from waitress import serve

app = Flask(__name__)


# --- Your /count_pixel route (simplified for testing) ---
@app.route("/count_pixel")
def count_pixel():
    client_ip = request.remote_addr

    # Normalize IPv4 / IPv6 / mapped IPv4 addresses
    try:
        ip_obj = ipaddress.ip_address(client_ip)
        if ip_obj.version == 6 and ip_obj.ipv4_mapped:
            client_ip = str(ip_obj.ipv4_mapped)
    except ValueError:
        pass

    print(f"Received request from {client_ip}")
    return jsonify({
        "normalized_ip": client_ip,
        "referer": request.headers.get("Referer"),
        "ip_version": ipaddress.ip_address(client_ip).version
    })


def run_server():
    # Dual-stack: works for both IPv4 and IPv6
    serve(app, host="::", port=8080)


# --- Start server in a background thread ---
thread = threading.Thread(target=run_server, daemon=True)
thread.start()

time.sleep(2)  # Give the server a moment to start

# --- Test requests ---
print("\n🚀 Sending test requests to localhost:8080\n")

# IPv4 request
try:
    resp4 = requests.get(
        "http://127.0.0.1:8080/count_pixel",
        headers={"Referer": "https://www.spolupropralesy.cz"}
    )
    print("IPv4 Response:", resp4.json())
except Exception as e:
    print("IPv4 test failed:", e)

# IPv6 request
try:
    resp6 = requests.get(
        "http://[::1]:8080/count_pixel",
        headers={"Referer": "https://www.spolupropralesy.cz"}
    )
    print("IPv6 Response:", resp6.json())
except Exception as e:
    print("IPv6 test failed:", e)

print("\nTest complete.\nKeep server running to manually test with curl if you like:")
print("  curl -4 http://127.0.0.1:8080/count_pixel")
print("  curl -6 http://[::1]:8080/count_pixel")
time.sleep(3)
