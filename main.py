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
@login_required
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
        login_user(User(result))
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

        if password != password_repeat:
            flash("Passwords do not match")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long")
        else:
            connection = connect_db()
            cursor = connection.cursor()
            try:
                cursor.execute("INSERT INTO `User` (`Name`,`Email`,`Password`,`Address`) VALUES (%s,%s,%s,%s)",
                               (name, email, password, address))
            except pymysql.err.IntegrityError:
                flash("User with that email already exists")
            else:
                connection.close()
                return redirect("/login")
            connection.close()
    return render_template("signup.html.jinja")

# -----------------------
# DONATE PAGES
# -----------------------
@app.route("/donations")
@login_required
def donate():
    return render_template("donate.html.jinja")

# -----------------------
# DONATE PAGE (LOAD DATA)
# -----------------------
@app.route("/donate", methods=["GET"])
@login_required
def donations():
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # Get items (for food dropdown)
    cursor.execute("SELECT ID, Name, Image FROM Items")
    food_types = cursor.fetchall()

    # Get fridges
    cursor.execute("SELECT ID, Name, Image FROM Fridge")
    fridges = cursor.fetchall()

    connection.close()

    return render_template(
        "donateinfo.html.jinja",
        fridges=fridges,
        food_types=food_types
    )


# -----------------------------
# 💰 DONATE MONEY
# -----------------------------
@app.route("/donate-money", methods=["GET", "POST"])
@login_required
def donate_money():
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        amount = request.form.get("amount")
        custom_amount = request.form.get("custom_amount")
        fridge_id = request.form.get("FridgeID")

        # Validation
        if not fridge_id:
            flash("Please select a fridge.")
            return redirect(url_for("donations"))

        try:
            fridge_id = int(fridge_id)
        except:
            flash("Invalid fridge selection.")
            return redirect(url_for("donations"))

        final_amount = custom_amount if custom_amount else amount
        if not final_amount:
            flash("Enter an amount.")
            return redirect(url_for("donations"))

        try:
            final_amount = float(final_amount)
        except:
            flash("Invalid amount.")
            return redirect(url_for("donations"))

        # Get fridge name
        cursor.execute("SELECT Name FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge = cursor.fetchone()
        fridge_name = fridge["Name"] if fridge else None

        # Insert donation
        cursor.execute("""
            INSERT INTO Donations
            (UserID, Amount, FridgeID, Email, Dropoff, Type, Description, Name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            current_user.id,
            final_amount,
            fridge_id,
            current_user.email,
            datetime.now(),
            "Money",                 # ✅ SAFE ENUM VALUE
            "Money Donation",
            fridge_name
        ))

        connection.commit()
        connection.close()

        flash("Donation successful!")
        return redirect(url_for("thank"))

    # GET
    cursor.execute("SELECT ID, Name, Image FROM Fridge")
    fridges = cursor.fetchall()

    # ALSO LOAD ITEMS (needed for page!)
    cursor.execute("SELECT ID, Name, Image FROM Items")
    food_types = cursor.fetchall()

    connection.close()

    return render_template(
        "donateinfo.html.jinja",
        fridges=fridges,
        food_types=food_types
    )


# -----------------------------
# 🍱 DONATE FOOD
# -----------------------------
@app.route("/donate-food", methods=["GET", "POST"])
@login_required
def donate_food():
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("food_email")
        dropoff_date = request.form.get("dropoff_date")
        fridge_id = request.form.get("FridgeID")
        quantity = request.form.get("quantity")
        food_type_id = request.form.get("food_type")  # ✅ comes from dropdown

        # --------------------
        # VALIDATION
        # --------------------
        if not fridge_id:
            flash("Select a fridge.")
            return redirect(url_for("donations"))

        try:
            fridge_id = int(fridge_id)
        except:
            flash("Invalid fridge.")
            return redirect(url_for("donations"))

        if not quantity or int(quantity) <= 0:
            flash("Enter valid quantity.")
            return redirect(url_for("donations"))

        if not food_type_id:
            flash("Select food type.")
            return redirect(url_for("donations"))

        try:
            food_type_id = int(food_type_id)
        except:
            flash("Invalid food type.")
            return redirect(url_for("donations"))

        # --------------------
        # GET FRIDGE NAME
        # --------------------
        cursor.execute("SELECT Name FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge = cursor.fetchone()
        fridge_name = fridge["Name"] if fridge else None

        # --------------------
        # GET ITEM NAME
        # --------------------
        cursor.execute("SELECT Name FROM Items WHERE ID=%s", (food_type_id,))
        item = cursor.fetchone()
        item_name = item["Name"] if item else "Food"

        # --------------------
        # INSERT (FIXED)
        # --------------------
        cursor.execute("""
            INSERT INTO Donations
            (UserID, FridgeID, Email, Dropoff, Type, Amount, Description, Name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            current_user.id,
            fridge_id,
            email,
            dropoff_date,
            "Food",             # ✅ FIXES DataError
            int(quantity),
            item_name,          # actual food type stored here
            fridge_name
        ))

        connection.commit()
        connection.close()

        flash("Food donation scheduled!")
        return redirect(url_for("thank"))

    # --------------------
    # GET PAGE DATA
    # --------------------
    cursor.execute("SELECT ID, Name, Image FROM Fridge")
    fridges = cursor.fetchall()

    cursor.execute("SELECT ID, Name, Image FROM Items")
    food_types = cursor.fetchall()

    connection.close()

    return render_template(
        "donateinfo.html.jinja",
        fridges=fridges,
        food_types=food_types
    )
# -----------------------
# INDIVIDUAL FRIDGE PAGE
# -----------------------

@app.route("/individfridge/<int:fridge_id>", methods=["GET","POST"])
@login_required
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
@login_required
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
