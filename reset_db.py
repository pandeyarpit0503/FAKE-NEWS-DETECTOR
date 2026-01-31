import os
import sqlite3

# Kill any running SQLite connections
db_path = 'fakenews.db'

try:
    # Delete the old database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✓ Deleted old database: {db_path}")
    else:
        print("Database file not found (may be in use)")
        
    # Also delete any WAL files
    for ext in ['-wal', '-shm']:
        if os.path.exists(db_path + ext):
            os.remove(db_path + ext)
            print(f"✓ Deleted {ext} file")
            
    print("\n✓ Database reset complete!")
    print("Now run: python app.py")
    
except Exception as e:
    print(f"Error: {e}")
    print("Make sure the server is stopped first (Ctrl+C)")











    