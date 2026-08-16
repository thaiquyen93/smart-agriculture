import subprocess

print("================================================================================")
print("🔍 INSPECTING SMURF-STREAM-ENGINE LOGS FOR BTC LEXATEK SERVER CONNECTION")
print("================================================================================\n")

res = subprocess.run("docker logs smurf-stream-engine --tail 40", shell=True, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr)
