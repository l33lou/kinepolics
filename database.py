# database.py
# All database schemas, initialization, and models are now self-contained in server.py.
# This file re-exports them for backwards compatibility.

from server import get_db, init_db, DB_PATH

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
