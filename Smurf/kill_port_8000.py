import subprocess
import re

print("================================================================================")
print("🔍 FINDING & KILLING PROCESS OCCUPYING PORT 8000")
print("================================================================ shower...\n")

res = subprocess.run("netstat -ano | findstr :8000", shell=True, capture_output=True, text=True)
output = res.stdout

if output:
    print("Found active connections on Port 8000:")
    print(output)
    lines = output.strip().split("\n")
    pids = set()
    for line in lines:
        parts = line.split()
        if len(parts) >= 5 and "LISTENING" in line:
            pids.add(parts[-1])
    
    for pid in pids:
        print(f"🗡️ Killing process PID: {pid}...")
        subprocess.run(f"taskkill /PID {pid} /F", shell=True)
    print("✅ Port 8000 freed successfully!")
else:
    print("ℹ️ Port 8000 is clean and available.")
