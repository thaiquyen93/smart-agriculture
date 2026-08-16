import subprocess

print("================================================================================")
print("🔍 CHECKING DOCKER CONTAINER STATUS FOR WEB-FRONTEND & WEB-BACKEND")
print("================================================================================\n")

res = subprocess.run("docker ps -a", shell=True, capture_output=True, text=True)
print(res.stdout)

print("\n--- DOCKER LOGS FOR WEB-FRONTEND ---")
res_fe = subprocess.run("docker logs smurf-web-frontend --tail 30", shell=True, capture_output=True, text=True)
print(res_fe.stdout)
if res_fe.stderr:
    print(res_fe.stderr)
