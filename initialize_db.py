import shelve
import os

# Define the path for the database file
db_path = os.path.join("database", "deliveries.db")

# Ensure the database folder exists
os.makedirs("database", exist_ok=True)

# Initialize the database with an empty list if it doesn't exist
with shelve.open(db_path) as db:
    if "deliveries" not in db:
        db["deliveries"] = []  # Create an empty list for deliveries
    if "selected_delivery" not in db:
        db["selected_delivery"] = {}  # Create an empty dictionary for selected delivery

print("Database initialized successfully.")
