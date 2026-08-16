import subprocess
import os

cwd = r"d:\Cac_Cuoc_Thi\Seal_Hackathon_SU26\Smurf\services\database-saver"
res = subprocess.run("python init_local_db.py", shell=True, cwd=cwd, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr)

res2 = subprocess.run("python test_db.py", shell=True, cwd=cwd, capture_output=True, text=True)
print(res2.stdout)
if res2.stderr:
    print(res2.stderr)
