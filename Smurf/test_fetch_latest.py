import urllib.request
import json

print("================================================================================")
print("🔍 FETCHING LIVE TELEMETRY FROM NESTJS BACKEND (http://localhost:8000/api/v1/telemetry/latest)")
print("================================================================\n")

try:
    req = urllib.request.urlopen("http://localhost:8000/api/v1/telemetry/latest", timeout=3)
    data = json.loads(req.read().decode())
    print(f"Items returned: {len(data)}")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error fetching from NestJS Backend: {e}")
