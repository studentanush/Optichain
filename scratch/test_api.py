import urllib.request
import json

url = "http://127.0.0.1:8000/api/demand/forecast"
data = {
    "product_id": "SKU-WS-001",
    "city": "City_A",
    "date": "2024-11-25",
    "campaign_active": True,
    "influencer": {
        "id": "INF-123",
        "followers": 1000000.0,
        "engagement_rate": 0.08,
        "platform": "instagram"
    }
}

req = urllib.request.Request(url)
req.add_header('Content-Type', 'application/json; charset=utf-8')
jsondata = json.dumps(data)
jsondataasbytes = jsondata.encode('utf-8')
req.add_header('Content-Length', len(jsondataasbytes))

try:
    with urllib.request.urlopen(req, jsondataasbytes) as response:
        res = response.read()
        print(f"Status: {response.getcode()}")
        print(f"Response: {json.dumps(json.loads(res), indent=2)}")
except urllib.error.HTTPError as e:
    print(f"Status: {e.code}")
    print(f"Response: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
