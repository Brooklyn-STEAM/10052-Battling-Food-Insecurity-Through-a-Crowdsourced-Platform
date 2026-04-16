from flask import Flask, render_template, request, flash, abort, jsonify, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
import pymysql
import random
from dynaconf import Dynaconf
import json
from flask_mail import Mail, Message

app = Flask(__name__)       
config = Dynaconf(settings_file=["settings.toml"])
app.secret_key = config.secret_key

DB_HOST = "db.steamcenter.tech" 
DB_USER = "smack"
DB_NAME = "fridge_net"

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:208576454@localhost/fridge_net'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TESTING'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'fridge.net5@gmail.com'
app.config['MAIL_PASSWORD'] = 'wfrj pqqt xlgh okpk' 
app.config['MAIL_DEFAULT_SENDER'] = 'fridge.net5@gmail.com' # Must match Username
app.config['MAIL_DEBUG'] = True

mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = "/login"

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
        self.role = result.get("Role", "user")
        self.address = result["Address"]
        self.id = result["ID"]
        self.profile_picture = result.get("ProfilePicture")

    def get_id(self):
        return str(self.id)

# -----------------------
# DATABASE CONNECTION
# -----------------------
def connect_db():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=config.password,
        database=DB_NAME,
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
# EMAIL FUNCTION
# -----------------------
def send_email(subject, recipients, name, confirm_url):
    msg = Message(
        subject=subject,
        recipients=recipients,
        sender=app.config['MAIL_DEFAULT_SENDER']
    )
    # Render both text and HTML bodies
    msg.body = render_template(f'email/welcome.txt', name=name, confirm_url=confirm_url)
    msg.html = render_template('email/emaildropoff.html.jinja', **data_dict)

    # Send the message within an app context if needed
    with app.app_context():
        mail.send(msg)

# -----------------------
# HOME
# -----------------------
@app.route("/")
def index():
    return render_template("homepage.html.jinja")

# -----------------------
# EMAIL
# -----------------------
@app.route('/send', methods=['GET', 'POST'])
def email():
    if request.method == 'POST':
        # Get data from the HTML form
        user_email = request.form.get('email')
        user_msg = request.form.get('message')

        # Create the email message
        msg = Message(subject="New Website Inquiry",
                      sender='your-email@gmail.com',
                      recipients=['your-personal-inbox@gmail.com']) # Where you want to receive it
        
        msg.body = f"Message from {user_email}:\n\n{user_msg}"
        
        mail.send(msg)
        return "Email sent successfully!"

    return render_template('donateinfo.html.jinja')
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


# -----------------------------
# 🍱 DONATE FOOD
# -----------------------------
fridges = [{"ID": 1, "Name": "Central Park Fridge", "Image": "/static/img1.jpg"}]
food_types = [{"ID": 1, "Name": "Canned Goods"}, {"ID": 2, "Name": "Fresh Produce"}]

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
        item_id = request.form.get("food_type")
        notes = request.form.get("notes") 

        # Fetch Fridge and Item names for the email
        cursor.execute("SELECT Name FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge_result = cursor.fetchone()
        fridge_name = fridge_result.get("Name", "Unknown Fridge") if fridge_result else "Unknown Fridge"
      
        cursor.execute("SELECT Name FROM Items WHERE ID=%s", (item_id,))
        item_result = cursor.fetchone()
        item_name = item_result.get("Name", "Unknown Item") if item_result else "Unknown Item"

        # Database Insert
        cursor.execute("""
            INSERT INTO Donations
            (UserID, FridgeID, Email, Dropoff, Type, Quantity, FoodCategory, Notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            current_user.id,
            fridge_id,
            email,
            dropoff_date,
            'food', 
            int(quantity) if quantity else 0,
            item_id,
            notes if notes and notes.strip() else None
        ))
        
        connection.commit()

        data_dict = {
            "full_name": full_name,
            "email": email,
            "dropoff_date": dropoff_date,
            "fridge_name": fridge_name,
            "quantity": quantity,
            "item_name": item_name,
            "notes": notes
        }

        try:
            with app.app_context():
                msg = Message(
                    subject=f"FridgeNet: Confirmation for your {item_name} donation",
                    recipients=[email]
                )
                msg.body = render_template('email/emailtext.txt', **data_dict)
                msg.html = render_template('email/emaildropoff.html.jinja', **data_dict)
                mail.send(msg)
        except Exception as e:
            print(f"Mail failed: {e}")

        connection.close()
        flash("Food donation scheduled and confirmation sent!")
        return redirect(url_for("thank"))

    # --- THIS SECTION RUNS ONLY ON 'GET' ---
    # Now that the POST block is finished, we fetch data to display the form
    cursor.execute("SELECT ID, Name, Image FROM Fridge")
    fridges_data = cursor.fetchall()

    cursor.execute("SELECT ID, Name, Image FROM Items")
    food_types_data = cursor.fetchall()

    connection.close()

    return render_template(
        "donateinfo.html.jinja",
        fridges=fridges_data,
        food_types=food_types_data
    )



@app.route("/individfridge/<int:fridge_id>", methods=["GET","POST"])
def personal_fridges(fridge_id):
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # --- 1. HANDLE POST (Review Submission) ---
    if request.method == "POST":
        rating = request.form.get("Rating")
        comment = request.form.get("Comment")
        
        if rating and comment:
            cursor.execute("""
                INSERT INTO Reviews (FridgeID, rating, comment, UserID, Timestamp) 
                VALUES (%s, %s, %s, %s, NOW())
            """, (fridge_id, rating, comment, current_user.id))
            connection.commit()
            
        connection.close()
        return redirect(url_for("personal_fridges", fridge_id=fridge_id))

    # --- 2. HANDLE GET (Page Display) ---
    # Fridge Info
    cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))
    fridge = cursor.fetchone()

    if not fridge:
        connection.close()
        abort(404)

    # ✅ MOVE THIS OUTSIDE THE if-block
    cursor.execute("""
        SELECT i.Name, i.Image, fi.Quantity 
        FROM Fridge_items fi
        JOIN Items i ON fi.ItemsID = i.ID 
        WHERE fi.FridgeID = %s AND fi.Quantity > 0
    """, (fridge_id,))
    items_list = cursor.fetchall()

    # Status
    cursor.execute("""
        SELECT Status, Last_updated 
        FROM Fridge_status 
        WHERE FridgeID=%s 
        ORDER BY Last_updated DESC, ID DESC LIMIT 1
    """, (fridge_id,))
    fridge_status = cursor.fetchone() or {
        "Status": "Unknown", 
        "Last_updated": datetime.now()
    }

    # Reviews
    cursor.execute("""
        SELECT r.rating AS Rating, r.comment AS Comment, r.Timestamp, u.Name AS user_name 
        FROM Reviews r 
        JOIN User u ON r.UserID = u.ID 
        WHERE r.FridgeID = %s 
        ORDER BY r.Timestamp DESC
    """, (fridge_id,))
    reviews = cursor.fetchall()

    connection.close()

    return render_template(
        "fridge.html.jinja",
        fridge=fridge,
        items=items_list,   # ✅ now correctly populated
        reviews=reviews,
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
            SELECT Status, Last_updated FROM Fridge_status 
            WHERE FridgeID=%s ORDER BY Last_updated DESC LIMIT 1
        """, (fridge_id,))
        
        # Store it in a variable named to match your template
        fridge_status_data = cursor.fetchone()

        current_time = datetime.now()
        connection.close()
        
        # In update_fridge GET:
        return render_template(
    "update_fridge.html.jinja",
    fridge=fridge,
    items=items,
    Fridge_status=fridge_status_data) # Match the name in the template!
        

    # -------- POST --------
    # Get fullness status once
    value = int(request.form.get("fullness", 2))
    mapping = ["empty", "few", "half", "many", "full"]
    status_value = mapping[value]

    # Update item quantities
    for key in request.form:
        if key.startswith("quantity_"):
            try:
                # Extract ID from the input name (e.g., "quantity_5" -> 5)
                item_id = int(key.split("_")[1])
                quantity = int(request.form[key])
            except (ValueError, IndexError):
                    continue

        if quantity <= 0:
            # If user sets it to 0, remove it from the fridge display
            cursor.execute("""
                DELETE FROM Fridge_items 
                WHERE FridgeID=%s AND ItemsID=%s
            """, (fridge_id, item_id))
        else:
            # This triggers the "UPDATE" because of the indexes in your screenshot
            cursor.execute("""
                INSERT INTO Fridge_items (FridgeID, ItemsID, Quantity)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Quantity = VALUES(Quantity)
            """, (fridge_id, item_id, quantity))

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

    if picture_url and not picture_url.startswith(("https://", "/static/")):
        flash("Invalid image URL")
        flash("Please provide a valid URL starting with https:// or a path to a static image.")
        return redirect("/profile_page")
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE User SET ProfilePicture = %s WHERE ID = %s",
        (picture_url or None, current_user.id)
    )

    connection.commit()  # ✅ THIS LINE FIXES IT
    connection.close()

    current_user.profile_picture = picture_url or None

    flash("Profile picture updated!")
    return redirect("/profile_page")

# -----------------------
# ABOUT PAGE 
# -----------------------
@app.route("/about")
def about():
    stats = {
        "meals": 12847,        # replace with real query
        "users": 642,
        "fridges": 25,
        "food_saved": 3.4      # tons (or calculate)
    }
    return render_template("aboutus.html.jinja", stats=stats)


# -----------------------
# FAVORITES 
# -----------------------
@app.route('/toggle-favorite', methods=['POST'])
@login_required 
def toggle_favorite():
    try:
        data = request.get_json()
        fridge_id = data.get('fridge_id')
        user_id = current_user.id 

        connection = connect_db()
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # 1. Match your DB: Favorites, UserID, FridgeID
        check_query = "SELECT * FROM Favorites WHERE UserID = %s AND FridgeID = %s"
        cursor.execute(check_query, (user_id, fridge_id))
        existing = cursor.fetchone()

        if existing:
            query = "DELETE FROM Favorites WHERE UserID = %s AND FridgeID = %s"
            message = "Removed"
        else:
            query = "INSERT INTO Favorites (UserID, FridgeID) VALUES (%s, %s)"
            message = "Added"

        cursor.execute(query, (user_id, fridge_id))
        connection.commit()
        connection.close()
        return jsonify({"message": message})

    except Exception as e:
        print(f"ERROR IN TOGGLE: {e}") # Check your terminal for this!
        return jsonify({"error": str(e)}), 500

@app.route('/get-favorites', methods=['GET'])
def get_favorites():
    if not current_user.is_authenticated:
        return jsonify([])

    connection = connect_db()
    try:
        # Use the standard cursor for your PyMySQL setup
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Matches Fridge (Singular), Favorites, ID, FridgeID, and UserID
        query = """
            SELECT f.* FROM Fridge f
            JOIN Favorites fav ON f.ID = fav.FridgeID
            WHERE fav.UserID = %s
        """
        cursor.execute(query, (current_user.id,)) 
        fav_fridges = cursor.fetchall()
        return jsonify(fav_fridges)
        
    except Exception as e:
        print(f"SQL Error in get_favorites: {e}")
        return jsonify([]), 500
    finally:
        connection.close()

# -----------------------
# CONTACT PAGE 
# -----------------------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        # --------------------
        # VALIDATION
        # --------------------
        if not name or not email or not message:
            flash("All fields are required.", "error")
            return redirect("/contact") 

        if len(message) < 10:
            flash("Message must be at least 10 characters.", "error")
            return redirect("/contact")

        # --------------------
        # DATABASE
        # --------------------
        connection = connect_db()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO Contacts (name, email, message)
                VALUES (%s, %s, %s)
            """, (name, email, message))

            connection.commit()

        except Exception as e:
            print("DB ERROR:", e)  # shows real issue in terminal
            connection.close()
            flash("Something went wrong. Please try again.", "error")
            return redirect("/contact")

        connection.close()

        # --------------------
        # SUCCESS
        # --------------------
        flash("Message sent successfully!", "success")
        return redirect("/contact")

    # --------------------
    # GET
    # --------------------
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

if __name__ == "__main__":
    app.run(debug=True)