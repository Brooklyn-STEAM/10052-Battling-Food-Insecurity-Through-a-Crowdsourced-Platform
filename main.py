from flask import Flask, render_template, request, flash, abort, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
import pymysql
import random
from dynaconf import Dynaconf
import json

app = Flask(__name__)    
config = Dynaconf(settings_file=["settings.toml"])
app.secret_key = config.secret_key

login_manager = LoginManager(app)
login_manager.login_view = "/login"

if __name__ == "__main__":
    app.run(debug=True)

# -----------------------
# USER CLASS
# -----------------------
class User:
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, result):
        self.name = result["Name"]
        self.email = result["Email"]
        self.address = result["Address"]
        self.id = result["ID"]
        self.role = result["Role"]

    def get_id(self):
        return str(self.id)

# -----------------------
# DATABASE CONNECTION
# -----------------------
def connect_db():
    return pymysql.connect(
        host="db.steamcenter.tech",
        user="smack",
        password=config.password,
        database="fridge_net",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

# -----------------------
# ERROR HANDLER
# -----------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("components/404.html.jinja"), 404

# -----------------------
# LOGIN MANAGER
# -----------------------
@login_manager.user_loader
def load_user(user_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM `User` WHERE `ID` = %s", (user_id,))
    result = cursor.fetchone()
    connection.close()
    if result:
        return User(result)
    return None

# -----------------------
# HOME
# -----------------------
@app.route("/")
def index():
    return render_template("homepage.html.jinja")

# -----------------------
# MAP PAGE (OPTIONAL TARGET FRIDGE)
# -----------------------
@app.route("/map")
def map_page():
    fridge_id = request.args.get("fridge_id")
    target_fridge = None

    if fridge_id:
        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute("SELECT ID, Name, Latitude, Longitude FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge = cursor.fetchone()
        connection.close()
        if fridge:
            target_fridge = {
                "id": fridge["ID"],
                "name": fridge["Name"],
                "lat": float(fridge["Latitude"]),
                "lng": float(fridge["Longitude"])
            }

    return render_template("map.html.jinja", target_fridge=target_fridge)

# -----------------------
# ROUTE TO SPECIFIC FRIDGE
# -----------------------
@app.route("/route/<int:fridge_id>")
def route_to_fridge(fridge_id):
    return redirect(url_for("map_page", fridge_id=fridge_id))

# -----------------------
# LOGIN / LOGOUT / SIGNUP
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM `User` WHERE `Email`=%s", (email,))
        result = cursor.fetchone()
        connection.close()
        
        if not result or result["Password"] != password:
                flash("Invalid email or password")
                return redirect(url_for("login"))

        user = User(result)
        login_user(user)

        if user.role == "restaurant":
            return redirect(url_for("restaurant_dashboard"))
        else:
            return redirect(url_for("index"))
    
    return render_template("login.html.jinja")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect("/")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        password_repeat = request.form["repeat_password"]
        address = request.form["address"]
        role = request.form.get("role")  # no default hiding bugs

        if not role:
            role = "user"

        if password != password_repeat:
            flash("Passwords do not match")
            return redirect("/signup")

        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM User WHERE Email = %s", (email,))
        if cursor.fetchone():
            connection.close()
            flash("Email already registered")
            return redirect("/signup")

        cursor.execute("""
            INSERT INTO User (Name, Email, Password, Address, Role)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, password, address, role))

        connection.commit()
        connection.close()

        return redirect("/login")

    return render_template("signup.html.jinja")
# -----------------------
# DONATE PAGES
# -----------------------
@app.route("/donations")
@login_required
def donate():
    return render_template("donate.html.jinja")

@app.route("/donate", methods=["GET"])
@login_required
def donations():
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Items")
    items = cursor.fetchall()
    cursor.execute("SELECT ID, Name, Image FROM Fridge")
    fridges = cursor.fetchall()
    connection.close()

    return render_template("donateinfo.html.jinja", items=items, fridges=fridges)



@app.route("/donate-money", methods=["POST"])
@login_required
def donate_money():
    amount = request.form.get("amount")
    custom_amount = request.form.get("custom_amount")
    fridge_id = request.form.get("FridgeID")  # matches your form

    if not fridge_id:
        flash("Please select a fridge to donate to.")
        return redirect(url_for("donations"))

    final_amount = custom_amount if custom_amount else amount

    # Validate amount
    if not final_amount:
        flash("Please select or enter an amount.")
        return redirect(url_for("donations"))

    try:
        final_amount = float(final_amount)
    except ValueError:
        flash("Invalid amount.")
        return redirect(url_for("donations"))

    # Connect and insert into DB
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO Donations (UserID, Amount, FridgeID, Email, Dropoff, Type, )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        current_user.id,
        final_amount,
        fridge_id,
        current_user.email,
        datetime.now(),
        "Money",
        "Monetary donation"
    ))
    connection.commit()
    connection.close()

    flash("Thank you for your monetary donation!")
    return redirect(url_for("thank"))
@app.route("/donate-food", methods=["POST"])
@login_required
def donate_food():
    dropoff_date = request.form.get("dropoff_date")
    food_type_id = request.form.get("food_type")
    notes = request.form.get("notes")
    fridge_id = request.form.get("FridgeID")
    quantity = request.form.get("quantity")
    name = request.form.get("full_name") or current_user.name

    # VALIDATION
    if not quantity or int(quantity) <= 0:
        flash("Please enter a valid quantity.")
        return redirect(url_for("donations"))

    if not dropoff_date:
        flash("Please select a drop-off date.")
        return redirect(url_for("donations"))

    if not food_type_id:
        flash("Please select a food type.")
        return redirect(url_for("donations"))

    if not fridge_id:
        flash("Please select a fridge.")
        return redirect(url_for("donations"))

    quantity = int(quantity)
    fridge_id = int(fridge_id)

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
INSERT INTO Donations 
(UserID, FridgeID, Email, Dropoff, Type, Quantity, Notes, Name)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""", (
    current_user.id,
    fridge_id,
    current_user.email,
    dropoff_date,
    type,
    quantity,
    notes,
    current_user.name
))

    connection.commit()
    connection.close()

    flash("Your food drop-off has been scheduled!")
    return redirect(url_for("thank"))

# -----------------------
# INDIVIDUAL FRIDGE PAGE
# -----------------------

@app.route("/individfridge/<int:fridge_id>", methods=["GET","POST"])
def personal_fridges(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()

    # Handle review submission
    if request.method == "POST":
        rating = request.form["Rating"]
        comment = request.form["Comment"]
        user_id = current_user.id if current_user.is_authenticated else None

        if not user_id:
            return "You must be logged in to review", 400

        cursor.execute(
            "INSERT INTO Reviews (FridgeID, rating, comment, UserID) VALUES (%s,%s,%s,%s)",
            (fridge_id, rating, comment, user_id)
        )
        connection.commit()
        return redirect(url_for("personal_fridges", fridge_id=fridge_id))

    # Load fridge info
    cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))
    fridge = cursor.fetchone()

    cursor.execute("""
    SELECT Status, Last_updated
    FROM Fridge_status
    WHERE FridgeID = %s
    ORDER BY Last_updated DESC
    LIMIT 1
""", (fridge_id,))
    fridge_status = cursor.fetchone()

    cursor.execute("""
        SELECT Reviews.*, User.name AS user_name
        FROM Reviews
        JOIN User ON Reviews.UserID = User.ID
        WHERE Reviews.FridgeID = %s
    """, (fridge_id,))
    reviews = cursor.fetchall()

    # 🔴 THIS is the important part: load real inventory
    cursor.execute("""
        SELECT
            Items.ID AS ItemsID,
            Items.Name,
            Items.Image,
            IFNULL(Fridge_items.Quantity, 0) AS Quantity
        FROM Items
        LEFT JOIN Fridge_items
        ON Items.ID = Fridge_items.ItemsID
        AND Fridge_items.FridgeID = %s
    """, (fridge_id,))
    items = cursor.fetchall()

    connection.close()

    if not fridge:
        abort(404)

    return render_template(
        "fridge.html.jinja",
        fridge=fridge,
        reviews=reviews,
        Items=items,
        fridge_status=fridge_status
    )



# -----------------------
# API: GET FRIDGES
# -----------------------
@app.route("/get-fridges")
def get_fridges():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT f.ID AS id, f.Name AS name, f.Latitude AS lat, f.Longitude AS lng,
        (SELECT Status FROM Fridge_status fs WHERE fs.FridgeID=f.ID ORDER BY Last_updated DESC LIMIT 1) AS status
        FROM Fridge f
    """)

    rows = cursor.fetchall()
    connection.close()
    fridges = []

    for row in rows:
        if row["lat"] and row["lng"]:
            fridges.append({
                "id": row["id"],
                "name": row["name"],
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
                "status": row["status"] or "Unknown"
            })

    return jsonify(fridges)

# -----------------------
# REPORT FRIDGE ISSUE
# -----------------------
@app.route("/report/<int:fridge_id>", methods=["GET","POST"])
@login_required
def report_fridge(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()

    if request.method == "POST":
        priority = request.form.get("priority")
        reproducibility = request.form.get("reproducibility")
        description = request.form.get("issue_description")
        user_id = current_user.id if current_user.is_authenticated else None

        cursor.execute("""
            INSERT INTO maintenance_reports
            (FridgeID, Reported_by, Description, Status, Timestamp, UserID, Priority, Reproducibility)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (fridge_id, user_id, description, "Open", datetime.now(), user_id, priority, reproducibility))
        connection.close()

        flash("Maintenance report submitted!")
        return redirect(url_for("index"))
    
    cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))

    fridge = cursor.fetchone()
    connection.close()

    if not fridge:
        abort(404)

    return render_template("report.html.jinja", fridge=fridge)

# -----------------------
# THANK YOU PAGE
# -----------------------
@app.route("/thank_you")
@login_required
def thank():
    return render_template("components/thanks.html.jinja")

# -----------------------
# UPDATE FRIDGE PAGE
# -----------------------
@app.route("/update_fridge/<int:fridge_id>", methods=["GET", "POST"])
@login_required
def update_fridge(fridge_id):

    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    current_time = datetime.now()
    # -------- GET --------
    if request.method == "GET":

        cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge = cursor.fetchone()

        cursor.execute("""
        SELECT
            Items.ID AS ItemsID,
            Items.Name,
            Items.Image,
            IFNULL(Fridge_items.Quantity, 0) AS Quantity
        FROM Items
        LEFT JOIN Fridge_items
        ON Items.ID = Fridge_items.ItemsID
        AND Fridge_items.FridgeID = %s
        """, (fridge_id,))
        items = cursor.fetchall()

        cursor.execute("""
        SELECT Status, Last_updated
        FROM Fridge_status
        WHERE FridgeID=%s
        ORDER BY Last_updated DESC
        LIMIT 1
        """, (fridge_id,))
        status = cursor.fetchone()

        connection.close()
        
        return render_template(
            "update_fridge.html.jinja",
            fridge=fridge,
            items=items,
            status={'Last_updated': current_time})
        

    # -------- POST --------
    # Get fullness status once
    value = int(request.form.get("fullness", 2))
    mapping = ["empty", "few", "half", "many", "full"]
    status_value = mapping[value]

    # Update item quantities
    for key in request.form:
        if key.startswith("quantity_"):

            item_id = key.split("_")[1]
            quantity = int(request.form[key])

            if quantity == 0:
                cursor.execute("""
                DELETE FROM Fridge_items
                WHERE FridgeID=%s AND ItemsID=%s
                """, (fridge_id, item_id))
            else:
                cursor.execute("""
                INSERT INTO Fridge_items (FridgeID, ItemsID, Quantity)
                VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE Quantity=%s
                """, (fridge_id, item_id, quantity, quantity))

    # Insert fridge status ONCE
    cursor.execute("""
    INSERT INTO Fridge_status (FridgeID, Status, Last_updated)
    VALUES (%s, %s, NOW())
""", (fridge_id, status_value))



    connection.commit()
    connection.close()

    return redirect(f"/individfridge/{fridge_id}")

# -----------------------
# PROFILE PAGE
# -----------------------
@app.route("/profile_page")
@login_required
def account():
    return render_template("components/profile.html.jinja")

@app.route("/profile/update-username", methods=["POST"])
@login_required
def update_username():
    username = request.form.get("username", "").strip()
    if not username:
        flash("Username cannot be empty")
        return redirect("/profile")
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET Name = %s WHERE ID = %s", (username, current_user.id))
    connection.close()
    current_user.name = username
    flash("Username updated!")
    return redirect("/profile_page")


@app.route("/profile/update-password", methods=["POST"])
@login_required
def update_password():
    password = request.form.get("password", "")
    if len(password) < 8:
        flash("Password must be at least 8 characters")
        return redirect("/profile")
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET Password = %s WHERE ID = %s", (password, current_user.id))
    connection.close()
    flash("Password updated!")
    return redirect("/profile_page")


@app.route("/profile/update-picture", methods=["POST"])
@login_required
def update_picture():
    picture_url = request.form.get("picture_url", "").strip()
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET ProfilePicture = %s WHERE ID = %s", (picture_url or None, current_user.id))
    connection.close()
    current_user.profile_picture = picture_url or None
    flash("Profile picture updated!")
    return redirect("/profile_page")
# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)

@app.route("/about")
def about():
    return render_template("aboutus.html.jinja")

@app.route("/contact")
def contact():
    return render_template("contact.html.jinja")


@app.route("/restaurants-connect", methods=["GET", "POST"])
def restaurants_connect():
    if request.method == "POST":
        name = request.form["restaurant_name"]
        contact = request.form["contact_person"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        food_type = request.form["food_type"]
        delivery = request.form["delivery_method"]
        

        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("""
        INSERT INTO restaurant_partners 
        (Name, Spokesperson, Email, Phone, Address, Food_type, Delivery_method)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, contact, email, phone, address, food_type, delivery))
       
        connection.commit()
        connection.close()

        return redirect("/thank_you")

    return render_template("restaurant_connect.html.jinja")

@app.route("/restaurant-dashboard")
@login_required
def restaurant_dashboard():
    if current_user.role != "restaurant":
        return redirect(url_for("index"))

    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # 1. TOTAL MEALS DONATED (impact metric)
    cursor.execute("""
        SELECT COALESCE(SUM(Quantity), 0) AS total_meals
        FROM Donations
        WHERE UserID = %s AND Type = 'food'
    """, (current_user.id,))
    total_meals = cursor.fetchone()["total_meals"]

    # 2. MONEY DONATIONS (optional extra metric)
    cursor.execute("""
        SELECT COALESCE(SUM(Quantity), 0) AS total_money
        FROM Donations
        WHERE UserID = %s AND Type = 'money'
    """, (current_user.id,))
    total_money = cursor.fetchone()["total_money"]

    # 3. SCHEDULED PICKUPS (future donations only)
    cursor.execute("""
    SELECT ID, Name, Quantity, Dropoff
    FROM Donations
    WHERE UserID = %s 
    AND Type = 'food'
    AND Dropoff >= CURDATE()
    ORDER BY Dropoff ASC
""", (current_user.id,))
    scheduled_list = cursor.fetchall()

    # 4. UPCOMING COUNT
    cursor.execute("""
        SELECT COUNT(*) AS scheduled
        FROM Donations
        WHERE UserID = %s 
        AND Type = 'food'
        AND Dropoff >= CURDATE()
    """, (current_user.id,))
    scheduled = cursor.fetchone()["scheduled"]
   
    connection.commit()
    connection.close()

    return render_template(
        "restaurant_dashboard.html.jinja",
        total_meals=total_meals,
        total_money=total_money,
        scheduled=scheduled,
        scheduled_list=scheduled_list
    )