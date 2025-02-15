import shelve

def inspect_db():
    db_path = "users.db"  # Path to your shelve database
    try:
        # Open the database
        with shelve.open(db_path) as db:
            print("Database contents:")
            for key, value in db.items():
                print(f"User: {key}, Data: {value}")
    except Exception as e:
        print(f"Error inspecting database: {e}")

if __name__ == "__main__":
    inspect_db()