import subprocess

print("================================================================================")
print("🔍 INSPECTING SMURF-STREAM-ENGINE DOCKER LOGS FOR BTC LIVE STREAM")
print("================================================================================\n")

res = subprocess.run("docker logs smurf-stream-engine --tail 50", shell=True, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr)
