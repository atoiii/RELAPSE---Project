import os
import re
import shelve

from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory

import Product
from createproduct import CreateProduct

app = Flask(__name__)

# folder for product images
base_directory = os.path.abspath(os.path.dirname(__file__))
upload_folder = os.path.join(base_directory, 'static')
extensions = {'png', 'jpg', 'jpeg'}
width = 300
height = 300

app.config['UPLOAD_FOLDER'] = upload_folder


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions


# REMOVE ANY SPECIAL CHARACTERS AND RIGHT FILE
def sanitize_filename(filename):
    filename = os.path.basename(filename)
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    return filename.lstrip('.')


def resize_image(image, width, height):
    img = Image.open(image)
    img.thumbnail((width, height))
    return img


@app.route('/static/<filename>')
def uploaded_file(filename):
    return send_from_directory("static", filename)


@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    # Your logic to add a product to cart
    return redirect(url_for('home'))


@app.route('/')
def home():
    """Display all products on home page."""
    db = shelve.open('products.db', 'c')
    products_dict = db.get('Products', {})  # Avoid KeyError
    db.close()

    products_list = list(products_dict.values())  # Convert to list for rendering
    return render_template('home.html', products=products_list)


@app.route('/admin/create_product', methods=['GET', 'POST'])
def create_product():
    if "admin" not in session:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("admin_login"))

    create_product_form = CreateProduct(request.form)

    if request.method == 'POST' and create_product_form.validate():
        file = request.files['product_image']

        if file and allowed_file(file.filename):
            filename = sanitize_filename(file.filename)
            img = resize_image(file, width, height)
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            img.save(img_path)

            with shelve.open("products.db", writeback=True) as db:
                products_dict = db.get('Products', {})

                product = Product.Product(filename,
                                          create_product_form.product_name.data,
                                          create_product_form.description.data,
                                          create_product_form.price.data
                                          )
                products_dict[product.get_product_id()] = product
                db['Products'] = products_dict

            flash("Product created successfully.", "success")
            return redirect(url_for("manage_products"))  # Redirects to manage products page

    return render_template("create_product.html", form=create_product_form)


@app.route('/admin/manage_products')
def manage_products():
    if "admin" not in session:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("admin_login"))

    db = shelve.open('products.db', 'c')
    products_dict = db.get('Products', {})
    db.close()

    products_list = list(products_dict.values())
    return render_template('manage_products.html', products_list=products_list, count=len(products_list))


@app.route('/admin/edit_product/<int:id>/', methods=['GET', 'POST'])
def edit_product(id):
    if "admin" not in session:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("admin_login"))

    edit_product_form = CreateProduct(request.form)
    db = shelve.open('products.db', 'c', writeback=True)
    products_dict = db.get('Products', {})

    product = products_dict.get(id)

    if request.method == 'POST' and edit_product_form.validate():
        file = request.files['product_image']
        if file and allowed_file(file.filename):
            filename = sanitize_filename(file.filename)
            img = resize_image(file, width, height)
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product.set_product_image(filename)

        product.set_product_name(edit_product_form.product_name.data)
        product.set_description(edit_product_form.description.data)
        product.set_price(edit_product_form.price.data)

        products_dict[id] = product
        db['Products'] = products_dict
        db.close()

        flash("Product updated successfully.", "success")
        return redirect(url_for('manage_products'))

    edit_product_form.product_name.data = product.get_product_name()
    edit_product_form.description.data = product.get_description()
    edit_product_form.price.data = product.get_price()

    db.close()
    return render_template('edit_product.html', form=edit_product_form)


@app.route('/admin/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    if "admin" not in session:
        flash("Please log in as an admin.", "danger")
        return redirect(url_for("admin_login"))

    db = shelve.open('products.db', 'w', writeback=True)
    products_dict = db.get('Products', {})

    if id in products_dict:
        products_dict.pop(id)

    db['Products'] = products_dict
    db.close()

    flash("Product deleted successfully.", "success")
    return redirect(url_for('manage_products'))


if __name__ == '__main__':
    app.run()
