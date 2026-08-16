import sys
import json
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

base_url = "http://localhost:8000/api/v1"

def check_get(endpoint):
    req = urllib.request.Request(f"{base_url}/{endpoint}")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))
        count = len(data) if isinstance(data, list) else data.get("total", len(data))
        print(f"✅ GET {endpoint:<25} -> Status 200 OK | Count: {count}")
        return data

print("=" * 80)
print("🚀 TESTING NESTJS WEB-BACKEND RESTFUL ENDPOINTS & VERIFICATION LOOPS")
print("=" * 80)

print("\n1. Health Check:")
health = check_get("health")
print("   • Service:", health.get("service"), "| WS Clients:", health.get("webSocketsClients"))

print("\n2. 6 Devices Telemetry & Freshness:")
devs = check_get("devices")
for d in devs:
    print(f"   • {d['device_code']:<10}: Status={d['status']:<7} | Age={d['age_sec']}s | Stale={d['is_stale']} | Metrics={d['metrics']}")

print("\n3. Irrigation Plans:")
plans = check_get("plans")
for p in plans.get("data", [])[:3]:
    print(f"   • [{p.get('plan_id')}] Area: {p.get('area_id')} | Water: {p.get('water_amount_liters')}L | Status: {p.get('status')}")

print("\n4. Inspection Tasks:")
tasks = check_get("tasks")
for t in tasks.get("data", [])[:3]:
    print(f"   • [{t.get('task_id')}] Device: {t.get('device_id')} | Status: {t.get('status')} | Verification: {t.get('verification_status')}")

print("\n5. Agent Reasoning Logs:")
logs = check_get("agent-logs")
for l in logs.get("data", [])[:2]:
    print(f"   • Agent: {l.get('agent_name')} | Action: {l.get('action_type')} | Evidence: {l.get('evidence_data')}")

print("\n6. Testing POST /api/v1/requests (Operator Trigger AI Coordinator):")
req_data = json.dumps({"prompt": "Hãy chuẩn bị kế hoạch tưới cho khu A", "session_id": "TEST-SESS-01"}).encode("utf-8")
post_req = urllib.request.Request(f"{base_url}/requests", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(post_req) as res:
    res_body = json.loads(res.read().decode("utf-8"))
    print("   ✅ POST /api/v1/requests -> Status:", res.status, "| Request ID:", res_body.get("request_id"))

print("\n7. Testing PATCH /api/v1/plans/:id/approve (Manager Verification Loop):")
if plans.get("data") and len(plans["data"]) > 0:
    plan_id = plans["data"][0]["plan_id"]
    patch_req = urllib.request.Request(f"{base_url}/plans/{plan_id}/approve", data=b"{}", headers={"Content-Type": "application/json"}, method="PATCH")
    with urllib.request.urlopen(patch_req) as res:
        res_body = json.loads(res.read().decode("utf-8"))
        print(f"   ✅ PATCH /plans/{plan_id}/approve -> Status:", res.status, "| Result:", res_body.get("message"))

print("\n8. Testing PATCH /api/v1/tasks/:id/verify (Field Maintenance Loop):")
if tasks.get("data") and len(tasks["data"]) > 0:
    task_id = tasks["data"][0]["task_id"]
    patch_req = urllib.request.Request(f"{base_url}/tasks/{task_id}/verify", data=b"{}", headers={"Content-Type": "application/json"}, method="PATCH")
    with urllib.request.urlopen(patch_req) as res:
        res_body = json.loads(res.read().decode("utf-8"))
        print(f"   ✅ PATCH /tasks/{task_id}/verify -> Status:", res.status, "| Result:", res_body.get("message"))

print("\n" + "=" * 80)
print("🎉 TOÀN BỘ 8 NHIỆM VỤ BACKEND HOÀN THÀNH 100%!")
print("=" * 80)
