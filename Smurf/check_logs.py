import subprocess

res = subprocess.run("docker logs smurf-stream-engine --tail 50", shell=True, capture_output=True, text=True)
print("=== DOCKER LOGS SMURF-STREAM-ENGINE ===")
print(res.stdout)
print(res.stderr)
