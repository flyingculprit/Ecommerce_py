from flask import Flask, render_template, request, redirect, session, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ============================
# MONGO CONNECTION
# ============================
client = MongoClient("")
db = client["Ecommerce"]

users = db.user
admins = db.admin
products = db.products
cart = db.cart

# ============================
# EMAIL OTP
# ============================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "@gmail.com"
app.config['MAIL_PASSWORD'] = ""

mail = Mail(app)

# ============================
# HOME
# ============================
@app.route('/')
def home():
    return redirect('/user-dashboard')

# ============================
# SIGNUP
# ============================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "POST":
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if users.find_one({"email": email}):
            return "Already Exists"

        otp = random.randint(100000, 999999)
        session["temp"] = {"name": name, "email": email, "password": password, "otp": otp}

        msg = Message("OTP Verification", sender="hdaprojectofficial@gmail.com", recipients=[email])
        msg.body = f"Your OTP: {otp}"
        mail.send(msg)

        return redirect('/verify-otp')

    return render_template("signup.html")

# ============================
# VERIFY OTP
# ============================
@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == "POST":
        if "temp" not in session:
            return "Expired"

        if str(session["temp"]["otp"]) == request.form['otp']:
            users.insert_one({
                "name": session["temp"]["name"],
                "email": session["temp"]["email"],
                "password": generate_password_hash(session["temp"]["password"])
            })
            session.pop("temp")
            return redirect('/login')

        return "Wrong OTP"

    return render_template("verify_otp.html")

# ============================
# LOGIN
# ============================
@app.route('/login', methods=['GET', 'POST'])
def login_user():
    error = None
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        user = users.find_one({"email": email})
        if not user:
            error = "User Not Found"
        elif not check_password_hash(user["password"], password):
            error = "Wrong Password"
        else:
            session["user"] = email
            session["name"] = user["name"]

            # Check if pre-login product exists
            if 'pre_login_cart' in session:
                product_id = session.pop('pre_login_cart')
                product = products.find_one({"_id": ObjectId(product_id)})

                if product and product["stock"] > 0:
                    existing = cart.find_one({"user": session["user"], "product_id": product_id})
                    if existing:
                        cart.update_one({"_id": existing["_id"]}, {"$inc": {"qty": 1}})
                    else:
                        cart.insert_one({
                            "user": session["user"],
                            "product_id": product_id,
                            "qty": 1
                        })

            return redirect('/cart')  # redirect to cart after login

    return render_template("login.html", error=error)

# ============================
# USER DASHBOARD
# ============================
@app.route('/user-dashboard')
def user_dashboard():
    items = list(products.find())
    name = session.get("name")
    return render_template("user_dashboard.html", products=items, name=name)

# ============================
# ADD TO CART
# ============================
@app.route('/add-to-cart/<id>', methods=['POST'])
def add_to_cart(id):
    if "user" not in session:
        session['pre_login_cart'] = id  # store for post-login
        return redirect('/login')

    product = products.find_one({"_id": ObjectId(id)})
    if product["stock"] <= 0:
        return "Out of Stock"

    existing = cart.find_one({"user": session["user"], "product_id": id})
    if existing:
        cart.update_one({"_id": existing["_id"]}, {"$inc": {"qty": 1}})
    else:
        cart.insert_one({"user": session["user"], "product_id": id, "qty": 1})

    return redirect('/cart')

# ============================
# CART PAGE
# ============================
@app.route('/cart')
def show_cart():
    if "user" not in session:
        return redirect('/login')

    user_cart = list(cart.find({"user": session["user"]}))
    final_cart = []
    total = 0
    for item in user_cart:
        product = products.find_one({"_id": ObjectId(item["product_id"])})
        total += int(product["price"]) * item["qty"]
        final_cart.append({"id": item["_id"], "product": product, "qty": item["qty"]})

    msg = request.args.get("msg")
    category = request.args.get("category")
    return render_template("cart.html", cart=final_cart, total=total, msg=msg, category=category)

# ============================
# REMOVE FROM CART
# ============================
@app.route('/remove/<id>', methods=['POST'])
def remove_item(id):
    cart.delete_one({"_id": ObjectId(id)})
    return redirect('/cart')

# ============================
# CHECK STOCK
# ============================
@app.route('/check-stock', methods=['POST'])
def check_stock():
    if "user" not in session:
        return jsonify({"success": False, "out_of_stock": []})

    user_items = list(cart.find({"user": session["user"]}))
    out_of_stock = []
    for item in user_items:
        product = products.find_one({"_id": ObjectId(item["product_id"])})
        if product["stock"] < item["qty"]:
            out_of_stock.append(product["name"])
    if out_of_stock:
        return jsonify({"success": False, "out_of_stock": out_of_stock})
    return jsonify({"success": True})

# ============================
# CHECKOUT
# ============================
@app.route('/checkout', methods=['POST'])
def checkout():
    if "user" not in session:
        return jsonify({"success": False, "msg": "Please login first!"})

    data = request.get_json()
    address = data.get("address")
    phone = data.get("phone")

    user_items = list(cart.find({"user": session["user"]}))
    total = 0
    order_details = []

    for item in user_items:
        product = products.find_one({"_id": ObjectId(item["product_id"])})
        if product["stock"] < item["qty"]:
            return jsonify({"success": False, "msg": f"{product['name']} is Out of Stock"})
        total += int(product["price"]) * item["qty"]
        order_details.append({"product": product["name"], "qty": item["qty"], "price": product["price"]})
        products.update_one({"_id": product["_id"]}, {"$inc": {"stock": -item["qty"]}})

    db.orders.insert_one({
        "user": session["user"],
        "items": order_details,
        "total": total,
        "address": address,
        "phone": phone,
        "date": datetime.now()
    })

    cart.delete_many({"user": session["user"]})
    return jsonify({"success": True, "msg": "Payment Successful! Order Placed!"})

# ============================
# ORDER HISTORY
# ============================
@app.route('/order-history')
def order_history():
    if "user" not in session:
        return redirect('/login')

    user_orders = list(db.orders.find({"user": session["user"]}).sort("date", -1))
    return render_template("order_history.html", orders=user_orders, email=session["user"])

# ============================
# ADMIN LOGIN
# ============================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        admin = admins.find_one({"username": username})
        if not admin:
            return "Admin Not Found"
        if check_password_hash(admin["password"], password):
            session["admin"] = username
            return redirect('/admin-dashboard')
        return "Wrong Password"

    return render_template("admin_login.html")

# ============================
# ADMIN DASHBOARD
# ============================
@app.route('/admin-dashboard')
def admin_dashboard():
    if "admin" not in session:
        return redirect('/admin-login')
    all_products = list(products.find())
    return render_template("admin_dashboard.html", products=all_products, admin=session["admin"])

# ============================
# ADD PRODUCT
# ============================
@app.route('/add-product', methods=['POST'])
def add_product():
    products.insert_one({
        "name": request.form["name"],
        "price": int(request.form["price"]),
        "stock": int(request.form["stock"]),
        "image": request.form["image"],
        "description": request.form["description"]
    })
    return redirect('/admin-dashboard')

# ============================
# EDIT PRODUCT
# ============================
@app.route('/edit/<id>')
def edit_page(id):
    if "admin" not in session:
        return redirect('/admin-login')
    product = products.find_one({"_id": ObjectId(id)})
    return render_template("edit_product.html", product=product)

# ============================
# UPDATE PRODUCT
# ============================
@app.route('/update-product/<id>', methods=['POST'])
def update_product(id):
    products.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "name": request.form["name"],
            "price": int(request.form["price"]),
            "stock": int(request.form["stock"]),
            "image": request.form["image"],
            "description": request.form["description"]
        }}
    )
    return redirect('/admin-dashboard')

# ============================
# DELETE PRODUCT
# ============================
@app.route('/delete/<id>', methods=['POST'])
def delete_product(id):
    products.delete_one({"_id": ObjectId(id)})
    return redirect('/admin-dashboard')

# ============================
# CART INCREASE / DECREASE
# ============================
@app.route('/cart/increase/<id>', methods=['POST'])
def increase_qty(id):
    cart.update_one({"_id": ObjectId(id)}, {"$inc": {"qty": 1}})
    return redirect('/cart')

@app.route('/cart/decrease/<id>', methods=['POST'])
def decrease_qty(id):
    item = cart.find_one({"_id": ObjectId(id)})
    if item["qty"] <= 1:
        cart.delete_one({"_id": item["_id"]})
    else:
        cart.update_one({"_id": ObjectId(id)}, {"$inc": {"qty": -1}})
    return redirect('/cart')

# ============================
# LOGOUT
# ============================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/user-dashboard')

# ============================
# RUN APP
# ============================
if __name__ == "__main__":
    app.run(debug=True)
