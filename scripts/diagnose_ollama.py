import requests
import json

BASE_URL = "http://localhost:11434"
CHAT_URL = f"{BASE_URL}/api/chat"
TAGS_URL = f"{BASE_URL}/api/tags"

def test_request(name, method, url, payload=None):
    print(f"--- Testing {name} ---")
    print(f"Method: {method}, URL: {url}")
    try:
        if method == "GET":
            resp = requests.get(url)
        else:
            resp = requests.post(url, json=payload)
        
        print(f"Status Code: {resp.status_code}")
        print(f"Headers: {resp.headers}")
        print(f"Response Body: {resp.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")
    print("\n")

if __name__ == "__main__":
    # 1. Baseline check - tags (known to work)
    test_request("Tags (GET)", "GET", TAGS_URL)

    # 2. Check chat endpoint with GET (expect 405 or 404)
    test_request("Chat (GET)", "GET", CHAT_URL)

    # 3. Check chat endpoint with POST empty payload
    test_request("Chat (POST Empty)", "POST", CHAT_URL, payload={})

    # 4. Check chat endpoint with full expected payload
    payload = {
        "model": "llama3",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False
    }
    test_request("Chat (POST Full)", "POST", CHAT_URL, payload=payload)
