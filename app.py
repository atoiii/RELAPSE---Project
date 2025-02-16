import os
import re
import shelve
import smtplib
from datetime import datetime
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify

app = Flask(__name__)
app.secret_key = "Relapsing"
app.config['SESSION_COOKIE_NAME'] = 'relapse_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript from accessing cookies
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Prevent cross-site request issues
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)  # For "Remember Me"
UPLOAD_FOLDER = "static/"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def home():
    with shelve.open("carousel.db") as db:
        carousel_items = list(db.values())  # Fetch all carousel items

    with shelve.open("products.db") as db:
        products = list(db.values())  # Fetch all products

    return render_template("home.html", products=products, carousel_items=carousel_items)


@app.route('/membership')
def membership():
    return render_template("membership.html")


@app.route('/sales')
def sales():
    with shelve.open("products.db") as db:
        products = [product for product in db.values() if product.get("sales")]  # Filter only sale products

    return render_template("sales.html", products=products)


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/clothing/<category>')
def clothing(category):
    category = category.lower()  # Normalize category to lowercase

    with shelve.open("products.db") as db:
        products = [db[key] for key in db.keys() if key.isdigit()]

    filtered_products = [product for product in products if product.get("category", "").lower() == category]

    if not filtered_products:
        flash(f"No products found in {category.capitalize()} category.", "info")

    return render_template("clothing.html", category=category.capitalize(), products=filtered_products)


class User:
    def __init__(self, first_name="Admin", last_name="User", email="", password="", role="user", membership_status="Regular", cart=None):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.role = role
        self.membership_status = membership_status
        self.cart = cart if cart is not None else []

    def to_dict(self):
        """Converts the User object to a dictionary for shelve storage."""
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "password": self.password,
            "role": self.role,
            "membership_status": self.membership_status,
            "cart": self.cart
        }

    @staticmethod
    def get_user(email):
        """Fetch user from database and convert to a User object."""
        with shelve.open("users.db") as db:
            user_data = db.get(email)
            if user_data:
                # **Ensure first_name & last_name exist (for admins)**
                user_data.setdefault("first_name", "Admin")
                user_data.setdefault("last_name", "User")
                return User(**user_data)
        return None


    @staticmethod
    def save_user(user):
        """Save or update user in shelve database."""
        with shelve.open("users.db", writeback=True) as db:
            db[user.email] = user.to_dict()

    @staticmethod
    def authenticate(email, password):
        """Check if user exists and password is correct."""
        user = User.get_user(email)
        return user if user and user.password == password else None


@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return render_template("signup.html")

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address!", "danger")
            return render_template("signup.html")

        if User.get_user(email):
            flash("Account already exists!", "danger")
        else:
            new_user = User(first_name, last_name, email, password)
            User.save_user(new_user)
            flash("Account created successfully!", "success")
            return redirect(url_for("login"))

    return render_template("signup.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        remember = "remember" in request.form

        user = User.authenticate(email, password)
        if user:
            session["user"] = user.to_dict()  # Store user data in session
            session["role"] = user.role
            session["cart"] = user.cart

            session.permanent = remember  # Set session persistence based on "Remember Me"

            # Redirect based on role
            if user.role == "superadmin":
                flash("Super Admin login successful!", "success")
                return redirect(url_for("super_admin_dashboard"))
            elif user.role == "admin":
                flash("Admin login successful!", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash(f"Welcome back, {user.first_name}!", "success")
                return redirect(url_for("profile"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route('/profile')
def profile():
    if "user" not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for("login"))

    user = User.get_user(session["user"]["email"])  # Load user from shelve
    return render_template("profile.html", user=user.to_dict())  # Pass as dict


@app.route('/cart', methods=["GET", "POST"])
def cart():
    if "user" not in session:
        flash("Please log in to access your cart.", "danger")
        return redirect(url_for("login"))

    if "cart" not in session:
        session["cart"] = []

    total_price = 0

    if request.method == "POST":
        with shelve.open("users.db", writeback=True) as db:
            user = session["user"]
            email = user["email"]

            if "product_id" in request.form:
                product_id = int(request.form["product_id"])
                size = request.form["size"]
                new_quantity = int(request.form["quantity"])

                if new_quantity >= 1:
                    for product in session["cart"]:
                        if product["id"] == product_id and product["size"] == size:
                            product["quantity"] = new_quantity
                            break

            if "remove_product_id" in request.form:
                product_id = int(request.form["remove_product_id"])
                size = request.form["size"]
                session["cart"] = [product for product in session["cart"] if
                                   not (product["id"] == product_id and product["size"] == size)]
                flash("Item removed from cart.", "success")

            db[email]["cart"] = session["cart"]

        session.modified = True
        return redirect(url_for("cart"))

    for product in session["cart"]:
        total_price += product["price"] * product["quantity"]

    return render_template("cart.html", cart=session["cart"], total_price=total_price,)


@app.route('/add_to_cart/<int:product_id>', methods=["GET", "POST"])
def add_to_cart(product_id):
    if "user" not in session:
        flash("Please log in to add items to your cart.", "danger")
        return redirect(url_for("login"))

    with shelve.open("products.db") as db:
        products = list(db.values())
    product = next((p for p in products if p["id"] == product_id), None)

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("home"))

    # Calculate discounted price if the product has a discount
    discount_percentage = product.get("discount_percentage", 0)  # Default to 0% if not set
    if discount_percentage > 0:
        product["discounted_price"] = round(product["price"] * (1 - discount_percentage / 100), 2)
    else:
        product["discounted_price"] = product["price"]

    product = next((p for p in list(shelve.open("products.db").values()) if p["id"] == product_id), None)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("home"))

    if request.method == "POST":
        size = request.form["size"]
        quantity = int(request.form["quantity"])

        if "cart" not in session:
            session["cart"] = []

        # Check if the product with the same size is already in the cart
        for item in session["cart"]:
            if item["id"] == product_id and item["size"] == size:
                item["quantity"] += quantity
                break
        else:
            session["cart"].append({
                "id": product_id,
                "name": product["name"],
                "price": product["price"],
                "size": size,
                "quantity": quantity
            })
        session.modified = True
        flash(f"{quantity} {size.upper()} {product['name']} added to cart!", "success")
        return redirect(url_for("cart"))

    return render_template("add_to_cart.html", product=product)


@app.route('/delivery', methods=["GET", "POST"])
def delivery():
    if "cart" not in session or len(session["cart"]) == 0:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("checkout"))

    if request.method == "POST":
        # Redirect to checkout after delivery details
        return redirect(url_for("checkout"))

    return render_template("delivery.html")


@app.route('/checkout', methods=["GET", "POST"])
def checkout():
    if "cart" not in session or len(session["cart"]) == 0:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("cart"))

    if request.method == "POST":
        session["cart"] = []  # Clear cart after payment
        session.modified = True
        flash("Payment successful! Your order has been placed.", "success")
        return redirect(url_for("CONFIRMATION"))

    return render_template("checkout.html")


@app.route('/CONFIRMATION')
def CONFIRMATION():
    return render_template('CONFIRMATION.html')


@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        with shelve.open("users.db") as db:
            if email in db:
                send_password_reset_email(email)
                flash("A password reset email has been sent to your email address.", "success")
                return redirect(url_for("login"))
            else:
                flash("Email not found!", "danger")

    return render_template("forgot_password.html")


@app.route('/reset_password', methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form["email"]
        new_password = request.form["new_password"]
        new_password_confirm = request.form["new_password_confirm"]

        if new_password != new_password_confirm:
            flash("Passwords do not match!", "danger")
            return render_template("reset_password.html")

        db = shelve.open("users.db")
        if email in db:
            user = db[email]
            user["password"] = new_password  # Update the password
            db[email] = user  # Reassign to persist changes
            flash("Password reset successfully!", "success")
            session.pop("user", None)
            return redirect(url_for("login"))
        else:
            flash("Email not found!", "danger")

    return render_template("reset_password.html")


@app.route('/logout')
def logout():
    if "user" in session:
        if "user" not in session or "email" not in session["user"]:
            return "Error: No user logged in"
        user_email = session["user"]["email"]  # Get the user's email
        with shelve.open("users.db", writeback=True) as db:
            if user_email in db:
                # Save the cart to the database before logging out
                db[user_email]["cart"] = session.get("cart", [])
    session.pop("user", None)  # Remove user from session
    session.pop("cart", None)  # Remove cart from session
    session.pop("role", None)
    resp = make_response(redirect(url_for("home")))
    resp.delete_cookie(app.config['SESSION_COOKIE_NAME'])  # Clear the session cookie
    flash("Logged out successfully.", "success")
    return resp


def send_password_reset_email(to_email):
    sender_email = "relapseshopco@gmail.com"  # Replace with your email
    sender_password = "swag zjmu bact zfbh"  # Replace with your email password
    subject = "Password Reset Request"
    body = f"""
    Hi,

    You requested a password reset. Please click the link below to reset your password:
    {url_for('reset_password', _external=True)}

    If you did not request this, please ignore this email.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Error sending email: {e}")


@app.route('/delete_account', methods=["GET", "POST"])
def delete_account():
    if "user" not in session:
        flash("You need to log in to delete your account.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        if "user" not in session or "email" not in session["user"]:
            return "Error: No user logged in"
        user_email = session["user"]["email"]  # Get the logged-in user's email

        # Open the database and delete the user's account
        with shelve.open("users.db") as db:
            if user_email in db:
                del db[user_email]  # Remove user from the database
                flash("Your account has been deleted successfully.", "success")

        # Log the user out after deleting the account
        session.pop("user", None)
        session.pop("cart", None)

        return redirect(url_for("home"))

    return render_template("delete_account.html")


@app.route('/super_admin_dashboard')
def super_admin_dashboard():
    # dashboard Admin
    if session.get('role') != 'superadmin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    return render_template("super_admin_dashboard.html")


@app.route("/add_carousel", methods=["GET", "POST"])
def add_carousel():
    if session.get("role") not in ["admin", "superadmin"]:
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("home"))

    if request.method == "POST":
        title = request.form["title"]
        caption = request.form["caption"]
        image = request.files["image"]

        if not title or not caption or not image:
            flash("All fields are required!", "danger")
            return redirect(url_for("add_carousel"))

        # Save the image to the static folder
        image_filename = os.path.join("static", image.filename)
        image.save(image_filename)

        # Save data in carousel.db with a simple, unique ID
        with shelve.open("carousel.db", writeback=True) as db:
            if db:
                new_id = max(map(int, db.keys())) + 1  # Get highest existing ID and increment
            else:
                new_id = 1  # Start from ID 1 if empty

            db[str(new_id)] = {
                "id": new_id,  # Store ID explicitly
                "image": image.filename,  # Path relative to /static
                "title": title,
                "caption": caption,
            }

        flash("Carousel item added successfully!", "success")
        return redirect(url_for("view_carousel"))

    return render_template("add_carousel.html")


@app.route("/view_carousel")
def view_carousel():
    if session.get("role") not in ["admin", "superadmin"]:
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("home"))

    with shelve.open("carousel.db") as db:
        carousel_items = list(db.values())

    return render_template("view_carousel.html", carousel_items=carousel_items)


@app.route("/edit_carousel/<item_id>", methods=["GET", "POST"])
def edit_carousel(item_id):
    if session.get("role") not in ["admin", "superadmin"]:
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("home"))

    with shelve.open("carousel.db", writeback=True) as db:
        if item_id not in db:
            flash("Carousel item not found.", "danger")
            return redirect(url_for("view_carousel"))

        item = db[item_id]

        if request.method == "POST":
            title = request.form["title"]
            caption = request.form["caption"]
            image = request.files["image"]

            if not title or not caption:
                flash("Title and caption are required!", "danger")
                return redirect(url_for("edit_carousel", item_id=item_id))

            # If a new image is uploaded, replace the old one
            if image:
                old_image_path = os.path.join("static", item["image"])

                # Delete the old image if it exists
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

                image_filename = os.path.join(app.config["UPLOAD_FOLDER"], image.filename)
                image.save(image_filename)
                item["image"] = image.filename  # Update image path

            item["title"] = title
            item["caption"] = caption
            db[item_id] = item  # Save updated details

            flash("Carousel item updated successfully!", "success")
            return redirect(url_for("view_carousel"))

    return render_template("edit_carousel.html", item=item, item_id=item_id)


@app.route("/delete_carousel/<item_id>", methods=["POST"])
def delete_carousel(item_id):
    if session.get("role") not in ["admin", "superadmin"]:
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("home"))

    with shelve.open("carousel.db", writeback=True) as db:
        if item_id in db:
            image_path = os.path.join("static", db[item_id]["image"])

            # Remove file if it exists
            if os.path.exists(image_path):
                os.remove(image_path)

            del db[item_id]  # Remove from database

            flash("Carousel item deleted successfully!", "success")
        else:
            flash("Carousel item not found.", "danger")

    return redirect(url_for("view_carousel"))


@app.route('/admin/create_admin', methods=["GET", "POST"])
def create_admin():
    if 'role' not in session:
        flash("You must be logged in to access this page.", "danger")
        return redirect(url_for("login"))
    elif session.get('role') != 'superadmin':
        flash("Only the Super Admin can create new admins.", "danger")
        return redirect(url_for("super_admin_dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Username and password cannot be empty.", "danger")
            return redirect(url_for("create_admin"))

        with shelve.open("users.db", writeback=True) as db:
            if db.get(email, {}).get('role') in ['admin', 'superadmin']:
                flash("Admin username already exists.", "danger")
            else:
                db[email] = {"email": email, "password": password, "role": "admin"}
                flash("New admin created successfully!", "success")
                return redirect(url_for("super_admin_dashboard"))

    return render_template("create_admin.html")


# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin to access the dashboard.", "danger")
        return redirect(url_for("login"))

    with shelve.open("users.db") as db:
        total_users = sum(1 for i in db if db.get(i, {}).get('role') not in ['admin', 'superadmin'])

    with shelve.open("products.db") as db:
        total_products = len(db)

    with shelve.open("sales.db") as db:
        total_sales = sum(db.values())

    return render_template("admin_dashboard.html", total_users=total_users, total_products=total_products,
                           total_sales=total_sales)


# ---------------- USER MANAGEMENT ----------------

@app.route('/admin/manage_users')
def manage_users():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    with shelve.open("users.db") as db:
        users = list(db.values())

    return render_template("manage_users.html", users=users)


@app.route('/admin/create_user', methods=["GET", "POST"])
def create_customer():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        email = request.form["email"]
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        password = request.form["password"]
        role = "user"

        # Open and write to the users.db
        with shelve.open("users.db", writeback=True) as db:
            if email in db:
                flash("A user with this email already exists.", "danger")
            else:
                db[email] = {"email": email, "first_name": first_name, "last_name": last_name, "password": password,
                             "membership_status": "Regular", "cart": [], "role": role}
                log_admin_action(f"Created user: {email}")
                flash("User created successfully.", "success")

    return render_template("create_customer.html")


@app.route('/admin/modify_customer/<email>', methods=["GET", "POST"])
def modify_customer(email):
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin to access this page.", "danger")
        return redirect(url_for("login"))

    with shelve.open("users.db", writeback=True) as db:
        customer = db.get(email)
        if not customer:
            flash("Customer not found.", "danger")
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            customer["first_name"] = request.form["first_name"]
            customer["last_name"] = request.form["last_name"]
            customer["email"] = request.form["email"]
            customer["membership_status"] = request.form["membership_status"]
            flash("Customer details updated successfully.", "success")
            return redirect(url_for("admin_dashboard"))

    return render_template("modify_customer.html", customer=customer)


@app.route('/admin/delete_user/<email>', methods=["POST"])
def delete_customer(email):
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    with shelve.open("users.db", writeback=True) as db:
        if email in db:
            del db[email]
            log_admin_action(f"Deleted user: {email}")
            flash("User deleted.", "success")

    return redirect(url_for("manage_users"))


# ---------------- PRODUCT MANAGEMENT ----------------

@app.route('/admin/manage_products')
def manage_products():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    with shelve.open("products.db") as db:
        products = list(db.values())

    return render_template("manage_products.html", products=products)


@app.route('/admin/manage_promo_codes')
def manage_promo_codes():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin to access this page.", "danger")
        return redirect(url_for("login"))

    return render_template("manage_promo_codes.html")


@app.route('/admin/create_product', methods=["GET", "POST"])
def create_product():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        category = request.form["category"]
        description = request.form["description"]
        image = request.files["image"]
        is_on_sale = request.form.get("sales") == "yes"
        discount_percentage = int(request.form["discount"]) if is_on_sale else 0

        if discount_percentage < 0:
            discount_percentage = 0
        elif discount_percentage > 90:
            discount_percentage = 90

        discounted_price = round(price * (1 - discount_percentage / 100), 2) if is_on_sale else price

        if image and image.filename:  # Ensure a file was uploaded
            # **Save Image Directly to Static Folder**
            image_path = os.path.join(app.root_path, 'static', image.filename)
            image.save(image_path)  # Save inside static/
            image_url = f"{image.filename}"  # Use the relative path for the image URL
        else:
            image_url = None  # Handle cases where no image is uploaded

        with shelve.open("products.db", writeback=True) as db:
            product_ids = [int(key) for key in db.keys() if key.isdigit()]
            product_id = max(product_ids) + 1 if product_ids else 1

            db[str(product_id)] = {
                "id": product_id,
                "name": name,
                "price": price,
                "category": category,
                "description": description,
                "image": image_url,
                "discounted_price": discounted_price if sales else None,
                "discount_percentage": discount_percentage if sales else 0,
                "sales": is_on_sale,
            }
            log_admin_action(f"Created product: {name} with discount {discount_percentage}%")
            flash("Product created successfully.", "success")

    return render_template("create_product.html")


@app.route('/admin/edit_product/<int:product_id>', methods=["GET", "POST"])
def edit_product(product_id):
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    with shelve.open("products.db", writeback=True) as db:
        product = db.get(str(product_id))

        if not product:
            flash("Product not found.", "danger")
            return redirect(url_for("manage_products"))

        if request.method == "POST":
            name = request.form["name"]
            price = float(request.form["price"])
            category = request.form["category"]
            description = request.form["description"]
            image = request.files["image"]
            is_on_sale = request.form.get("sales") == "yes"

            discount_percentage = float(request.form.get("discount", 0))
            if discount_percentage < 0:
                discount_percentage = 0
            elif discount_percentage > 90:
                discount_percentage = 90

            discounted_price = round(price * (1 - discount_percentage / 100), 2) if sales else price

            # If a new image is uploaded, replace the old one
            if image and image.filename:
                # Save the new image
                image_path = os.path.join(app.root_path, 'static', image.filename)
                image.save(image_path)
                image_url = image.filename
            else:
                # Keep the current image if no new image is uploaded
                image_url = product["image"]

            # Update product details
            product["name"] = name
            product["price"] = price
            product["discounted_price"] = discounted_price if sales else None
            product["category"] = category
            product["description"] = description
            product["image"] = image_url
            product["sales"] = is_on_sale
            product["discount_percentage"] = discount_percentage if sales else 0

            db[str(product_id)] = product  # Save updated product to db

            flash("Product updated successfully.", "success")
            return redirect(url_for("manage_products"))

    return render_template("edit_product.html", product=product)


@app.route('/admin/delete_product/<int:product_id>', methods=["POST"])
def delete_product(product_id):
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    with shelve.open("products.db", writeback=True) as db:
        product = db.get(str(product_id))

        if product:
            # Remove the image file from static folder
            image_path = os.path.join(app.root_path, 'static', product["image"])
            if os.path.exists(image_path):
                os.remove(image_path)

            # Delete product from database
            del db[str(product_id)]
            flash("Product deleted successfully.", "success")
        else:
            flash("Product not found.", "danger")

    return redirect(url_for("manage_products"))


# ---------------- ADMIN CHANGELOG ----------------

@app.route('/admin/changelog')
def admin_changelog():
    if session.get('role') not in ['admin', 'superadmin']:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("login"))

    with shelve.open("admin_logs.db") as db:
        logs = list(db.values())

    return render_template("admin_changelog.html", changelog=logs)


def log_admin_action(action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with shelve.open("admin_logs.db", writeback=True) as db:
        db[str(len(db) + 1)] = {"timestamp": timestamp, "admin": session.get("user", {}).get("email", "Unknown"),
                                "action": action}


if __name__ == "__main__":
    app.secret_key = 'secret_key'

DB_FILE = "deliveries.db"


def get_deliveries():
    with shelve.open(DB_FILE) as db:
        return db.get("deliveries", [])


def save_deliveries(deliveries):
    with shelve.open(DB_FILE, writeback=True) as db:
        db["deliveries"] = deliveries


def get_selected_delivery():
    with shelve.open(DB_FILE) as db:
        return db.get("selected_delivery", {})


def save_selected_delivery(selected_delivery):
    with shelve.open(DB_FILE, writeback=True) as db:
        db["selected_delivery"] = selected_delivery


@app.route('/')
def index():
    deliveries = get_deliveries()
    selected_delivery = get_selected_delivery()
    return render_template('website.html', deliveries=deliveries, selected_delivery=selected_delivery)


@app.route('/add_delivery', methods=['POST'])
def add_delivery():
    country = request.form.get('country')
    address = request.form.get('address')
    city = request.form.get('city')
    state = request.form.get('state')
    postcode = request.form.get('postcode')

    if country and address and city:
        deliveries = get_deliveries()
        deliveries.append({
            'country': country,
            'address': address,
            'city': city,
            'state': state,
            'postcode': postcode
        })
        save_deliveries(deliveries)
        flash('Delivery added successfully!', 'success')
    else:
        flash('All fields are required to add a delivery!', 'danger')

    return redirect(url_for('checkout'))


@app.route('/edit_delivery/<int:index>', methods=['GET', 'POST'])
def edit_delivery(index):
    deliveries = get_deliveries()

    if request.method == 'POST':
        if 0 <= index < len(deliveries):
            deliveries[index] = {
                'country': request.form.get('country'),
                'address': request.form.get('address'),
                'city': request.form.get('city'),
                'state': request.form.get('state'),
                'postcode': request.form.get('postcode')
            }
            save_deliveries(deliveries)
            flash('Delivery updated successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('edit_delivery.html', delivery=deliveries[index], index=index)


@app.route('/delete_delivery/<int:index>', methods=['POST'])
def delete_delivery(index):
    deliveries = get_deliveries()
    selected_delivery = get_selected_delivery()

    if 0 <= index < len(deliveries):
        if deliveries[index] == selected_delivery:
            selected_delivery = {}
            save_selected_delivery(selected_delivery)

        deliveries.pop(index)
        save_deliveries(deliveries)
        flash('Delivery deleted successfully!', 'success')
    else:
        flash('Invalid delivery index for deletion!', 'danger')

    return redirect(url_for('index'))


@app.route('/select_delivery/<int:index>', methods=['POST'])
def select_delivery(index):
    deliveries = get_deliveries()

    if 0 <= index < len(deliveries):
        selected_delivery = deliveries[index]
        save_selected_delivery(selected_delivery)
        flash('Delivery selected successfully!', 'success')
    else:
        flash('Invalid delivery selection!', 'danger')

    return redirect(url_for('index'))


@app.route('/membership_payment')
def membership_payment():
    return render_template('membership_payment.html')


def update_membership(User, status):
    with shelve.open('users.db', writeback=True) as db:
        if User in db:
            db[User]['membership_status'] = status  # Update membership status
        else:
            print("User not found")


@app.route("/purchase_membership", methods=["POST"])
def purchase_membership():
    if "user" not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401

    data = request.json
    membership = data.get("membership")

    if membership not in ["Bronze", "Silver", "Gold"]:
        return jsonify({"success": False, "message": "Invalid membership selected"}), 400

    user = session["user"]  # Retrieve logged-in user

    # Update membership in the database
    with shelve.open('users.db', writeback=True) as db:
        if user in db:
            db[user]['membership_status'] = membership
            return jsonify({"success": True, "message": f"Membership upgraded to {membership}!"})
        else:
            return jsonify({"success": False, "message": "User not found"}), 404


if __name__ == "__main__":
    app.run(debug=True)
