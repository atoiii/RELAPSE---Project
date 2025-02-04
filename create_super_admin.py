import shelve

def create_super_admin():
    """Creates the first Super Admin manually in the database."""
    with shelve.open("admins.db", writeback=True) as db:
        super_admin_username = "superadmin"
        super_admin_password = "R3L4P534DM1N"

        if super_admin_username not in db:
            db[super_admin_username] = {
                "username": super_admin_username,
                "password": super_admin_password,
                "role": "superadmin"  # Mark as the Super Admin
            }
            print("✅ Super Admin created successfully!")
        else:
            print("⚠️ Super Admin already exists!")

if __name__ == "__main__":
    create_super_admin()
