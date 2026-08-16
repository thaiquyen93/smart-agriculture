import subprocess

print("================================================================================")
print("🔍 INSPECTING RECENT GIT COMMITS & MERGES")
print("================================================================\n")

res = subprocess.run("git log -n 5 --oneline", shell=True, capture_output=True, text=True)
print("RECENT COMMITS:")
print(res.stdout)

res_status = subprocess.run("git status", shell=True, capture_output=True, text=True)
print("\nGIT STATUS:")
print(res_status.stdout)
