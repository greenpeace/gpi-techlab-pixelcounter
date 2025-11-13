import requests

# --- Configuration ---
LOCAL_URL = "http://localhost:8080/count_pixel"
PROD_URL = "https://counter.greenpeace.org/count_pixel"  # replace with your actual prod URL
QUERY = "?id=gpcztestcounter&email_hash=4992b176c86064af46bcceec9a9d1a18a619ea34b1e"

# Simulated GTM headers
GTM_HEADERS = {
    "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "accept-language": "cs-CZ,cs;q=0.9",
    "priority": "i",
    "referer": "https://www.spolupropralesy.cz",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "image",
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "cross-site",
    "sec-fetch-storage-access": "none",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, \
        like Gecko) Chrome/140.0.0.0 Safari/537.36",
    # Simulate IPv6 forwarding from Google Tag Manager
    "X-Forwarded-For": "2001:2043:3c45:4000:fcc9:10a0:3516:c629"
}


def test_url(label, url):
    print(f"\n Testing {label} — {url}")
    try:
        response = requests.get(url + QUERY, headers=GTM_HEADERS, timeout=10)
        print(f"Status: {response.status_code}")
        content_type = response.headers.get("content-type", "")
        if "json" in content_type or "text" in content_type:
            print("Response text:", response.text[:400])
        else:
            print(f"Binary response (e.g. GIF) with size: {len(response.content)} bytes")
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    test_url("LOCALHOST", LOCAL_URL)
    test_url("PRODUCTION", PROD_URL)
