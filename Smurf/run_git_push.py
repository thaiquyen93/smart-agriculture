import subprocess
import os
import sys

REPO_URL = "https://github.com/seal-hackathon-fptu/smurf_su2026.git"
PROJECT_DIR = r"d:\Cac_Cuoc_Thi\Seal_Hackathon_SU26\Smurf"

def run_cmd(cmd):
    print(f"🚀 Running: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr)
    return res.returncode

print("================================================================================")
print("📦 SMURF HACKATHON GITHUB COMMIT & PUSH TOOL")
print(f"📌 Target Remote: {REPO_URL}")
print("================================================================================\n")

run_cmd("git init")
run_cmd("git remote remove origin")
run_cmd(f"git remote add origin {REPO_URL}")
run_cmd("git branch -M main")
run_cmd("git add .")
run_cmd('git commit -m "feat: initialize Smurf Smart Agriculture platform with MQTT stream engine, simulator, and multi-agent architecture"')

print("\n📡 Đang đẩy (Push) codebase lên GitHub Repository...")
code = run_cmd("git push -u origin main")

if code == 0:
    print("\n🎉 PUSH THÀNH CÔNG 100% LÊN GITHUB REPOSITORY!")
    print(f"🔗 Xem trên GitHub: {REPO_URL}")
else:
    print("\n⚠️ Nếu lệnh push báo lỗi authentication/permission, bạn hãy tự gõ lệnh trong Terminal:")
    print("   git push -u origin main --force")
