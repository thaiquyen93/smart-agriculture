import requests
import json
import time

url = "http://localhost:5000/api/process"
payload = {
    "soil_moisture": [50.1, 50.2, 50.3, 50.4, 50.5, 50.6, 50.7, 50.8, 50.9, 51.0],
    "temperature": [25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9, 26.0],
    "humidity": [60.1, 60.2, 60.3, 60.4, 60.5, 60.6, 60.7, 60.8, 60.9, 61.0],
    "flow_rate": [10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 11.0],
    "power": [100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7, 100.8, 100.9, 101.0],
    "ph": [7.1, 7.1, 7.1, 7.1, 7.1, 7.1, 7.1, 7.1, 7.1, 7.1],
    "level": [80.1, 80.2, 80.3, 80.4, 80.5, 80.6, 80.7, 80.8, 80.9, 81.0],
    "lux": [10000.0, 10010.0, 10020.0, 10030.0, 10040.0, 10050.0, 10060.0, 10070.0, 10080.0, 10090.0]
}

retries = 5
for i in range(retries):
    try:
        print(f"Sending request to API... (Attempt {i+1})")
        response = requests.post(url, json=payload, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        break
    except Exception as e:
        print(f"Failed to connect: {e}")
        time.sleep(2)
