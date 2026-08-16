import sys
from pathlib import Path

# Add current dir to path
sys.path.append(str(Path(__file__).parent))

from db import DatabaseManager

print("Initializing local SQLite Database file...")
db = DatabaseManager()
print(f"✓ Database file created at: {db.db_path}")
