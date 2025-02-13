from wtforms import Form, StringField, FileField, validators


class CreateProduct(Form):
    product_image = FileField('Upload Product Image')
    product_name = StringField('Product Name', [validators.Length(min=1, max=150), validators.DataRequired()])
    description = StringField('Description', [validators.Length(min=10, max=1000), validators.DataRequired()])
    price = StringField('Price', [validators.DataRequired()])
