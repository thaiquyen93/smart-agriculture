import urllib.request
import json

print("================================================================================")
print("🔍 CHECKING NESTJS BACKEND HEALTH (http://localhost:8000/api/v1/health)")
print("================================================================\n")

try:
    req = urllib.request.urlopen("http://localhost:8000/api/v1/health", timeout=3)
    data = json.loads(req.read().decode())
    print("✅ NestJS Backend is ONLINE!")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"❌ Cannot connect to NestJS Backend on http://localhost:8000: {e}")
