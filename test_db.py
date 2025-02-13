# import shelve
#
# # Open the database
# with shelve.open("products.db") as db:
#     products_dict = db.get('Products', {})
#
#     # Check if products exist
#     if not products_dict:
#         print("No products found in the database.")
#     else:
#         print("Products found:")
#         for product_id, product in products_dict.items():
#             print(f"ID: {product_id}")
#             print(f"Name: {product.get_product_name()}")
#             print(f"Image: {product.get_product_image()}")
#             print(f"Description: {product.get_description()}")
#             print(f"Price: {product.get_price()}")
#             print("-" * 30)
