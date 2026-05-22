from flask import Flask, render_template, request, flash, abort, jsonify, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timezone, timedelta
import pymysql
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
import random
from dynaconf import Dynaconf
import json
from flask_mail import Mail, Message
import smtplib, hashlib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import CSRFProtect


app = Flask(__name__)      
config = Dynaconf(settings_file=["settings.toml"])
app.secret_key = config.secret_key
csrf = CSRFProtect(app)

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

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000000000 per day", "100000 per hour"]
)


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
       self.id = result.get("ID")
       self.name = result.get("Name")
       self.email = result.get("Email")
       self.address = result.get("Address")
       self.role = result.get("Role", "user")
       self.profile_picture = result.get("ProfilePicture") or result.get("profile_picture")

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

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

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
def send_email(subject, recipients, template_txt, template_html, context=None):
    msg = Message(
        subject=subject,
        recipients=recipients,
        sender=app.config.get('MAIL_DEFAULT_SENDER')
    )

    context = context or {}

    msg.body = render_template(template_txt, **context)
    msg.html = render_template(template_html, **context)

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
def email_inquiry():
    if request.method == 'POST':
        # Get data from the HTML form
        user_email = request.form.get('email')
        user_msg = request.form.get('message')

        if not user_email or not user_msg:
            return "Missing email or message", 400

        # Create the email message
        msg = Message(
            subject="New Website Inquiry",
            sender=app.config.get('MAIL_DEFAULT_SENDER'),
            recipients=['your-personal-inbox@gmail.com'] 
        )
      
        msg.body = f"Message from {user_email}:\n\n{user_msg}"
      
        try:
            mail.send(msg)
            # It's better to redirect back to a page with a success message
            return "Email sent successfully!"
        except Exception as e:
            return f"Failed to send email: {str(e)}", 500

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
# LOGIN PAGE
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")

        connection = connect_db()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT * FROM `User` WHERE `Email`=%s",
                (email,)
            )
            result = cursor.fetchone()

        finally:
            cursor.close()
            connection.close()

        # 1. Validate user exists
        if not result:
            flash("Invalid email or password", "login_error")
            return redirect(url_for("login"))

        # 2. Validate password (ONLY ONCE, hashed)
        if not check_password_hash(result["Password"], password):
            flash("Invalid email or password", "login_error")
            return redirect(url_for("login"))

        # 3. Login user
        user = User(result)
        login_user(user)

        flash("Logged in successfully!", "login_success")

        if user.role == "restaurant":
            return redirect(url_for("restaurant_dashboard"))

        return redirect(url_for("index"))

    return render_template("login.html.jinja")

# --------------------
# LOGOUT FUNCTION 
# --------------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect("/")

# --------------------
# SIGNUP PAGE 
# --------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():

    # 1. Block already logged-in users
    if current_user.is_authenticated:
        flash("You are already logged in.", "signup_info")
        return redirect(url_for("index"))

    if request.method == "POST":

        # 2. Collect form data
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        password_repeat = request.form["repeat_password"]
        address = request.form["address"]
        birthdate = request.form.get("birthdate")
        role = request.form.get("role") or "user"

        default_pic = "/static/images/default-profile.png"

        # 3. Basic validation (NO DB)
        if password != password_repeat:
            flash("Passwords do not match.", "signup_error")
            return redirect(url_for("signup"))

        if len(password) < 8:
            flash("Password must be at least 8 characters long", "signup_error")
            return redirect(url_for("signup"))

        # 4. Age check
        if birthdate:
            birthdate_obj = datetime.strptime(birthdate, "%Y-%m-%d")
            today = datetime.today()

            age = today.year - birthdate_obj.year - (
                (today.month, today.day) < (birthdate_obj.month, birthdate_obj.day)
            )

            if age < 18:
                flash("You must be 18 or older to create an account.", "signup_error")
                return redirect(url_for("signup"))

        connection = connect_db()
        cursor = connection.cursor()

        try:
            # 5. Check duplicate email FIRST
            cursor.execute("SELECT 1 FROM User WHERE Email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered.", "signup_error")
                return redirect(url_for("signup"))

            # 6. Hash password
            hashed_password = generate_password_hash(password)

            # 7. Insert user
            cursor.execute("""
                INSERT INTO User (Name, Email, Password, Address, Role, ProfilePicture)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, email, hashed_password, address, role, default_pic))

            connection.commit()

        except pymysql.err.IntegrityError:
            flash("Email is already in use.", "signup_error")
            return redirect(url_for("signup"))

        finally:
            cursor.close()
            connection.close()

        flash("Account created successfully! Please log in.", "signup_success")
        return redirect(url_for("login"))

    # 8. GET request
    max_birthdate = f"{datetime.utcnow().year - 18}-12-31"
    return render_template("signup.html.jinja", max_birthdate=max_birthdate)
# -----------------------
# DONATE PAGES
# -----------------------
@app.route("/donations")
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
        fridge_id = request.form.get("money_fridge_id")  # ✅ FIXED

        if not fridge_id:
            flash("Please select a fridge.", "donation_error")
            return redirect(url_for("donations"))

        try:
            fridge_id = int(fridge_id)
        except:
            flash("Invalid fridge selection.", "donation_error")
            return redirect(url_for("donations"))

        if custom_amount:
            final_amount = custom_amount
        elif amount:
            final_amount = amount
        else:
            flash("Enter an amount.", "donation_error")
            return redirect(url_for("donations"))

        try:
            final_amount = float(final_amount)
        except:
            flash("Invalid amount.", "donation_error")
            return redirect(url_for("donations"))

        cursor.execute("SELECT Name FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge = cursor.fetchone()
        fridge_name = fridge["Name"] if fridge else None

        cursor.execute("""
             INSERT INTO Donations
            (UserID, FridgeID, Email, Dropoff, Type, Quantity, Notes)
             VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
            current_user.id,
            fridge_id,
            current_user.email,
            datetime.now().date(),
            "money",
            int(float(final_amount)),
            "Money Donation"
            ))

        connection.commit()
        connection.close()
        flash("Thank you for your donation!", "donation_success")
        return redirect(url_for("thank"))

    cursor.execute("SELECT ID, Name, Image FROM Fridge")
    fridges = cursor.fetchall()

    cursor.execute("SELECT ID, Name, Image FROM Items")
    food_types = cursor.fetchall()

    connection.close()

    return render_template("donateinfo.html.jinja", fridges=fridges, food_types=food_types)

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
        # 1. Retrieve and Clean Data
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("food_email", "").strip()
        dropoff_date = request.form.get("dropoff_date")
        fridge_id = request.form.get("FridgeID")  
        quantity = request.form.get("quantity")
        item_id = request.form.get("food_type")   
        notes = request.form.get("notes", "").strip()

        # ---------------------------------------------------------
        # 2. VALIDATION
        # ---------------------------------------------------------
        if not all([fridge_id, item_id, quantity, email]):
            flash("Missing required information. Please check all fields.", "donation_error")
            return redirect(url_for("donations"))

        try:
            # 3. Lookup Names for the Email
            cursor.execute("SELECT Name FROM Fridge WHERE ID=%s", (fridge_id,))
            fridge_result = cursor.fetchone()
            fridge_name = fridge_result['Name'] if fridge_result else "Community Fridge"
         
            cursor.execute("SELECT Name FROM Items WHERE ID=%s", (item_id,))
            item_result = cursor.fetchone()
            item_name = item_result['Name'] if item_result else "Food Item"

            # 4. Database Insert
            cursor.execute("""
                INSERT INTO Donations 
                (UserID, FridgeID, Email, Dropoff, Type, Quantity, FoodCategory, Notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                current_user.id,
                int(fridge_id),
                email,
                dropoff_date,
                'food',
                int(quantity),
                int(item_id),
                notes if notes else None
            ))
           
            connection.commit()

            # 5. Protected Email Logic
            # We put this in a nested try so the user still reaches the Thank You page
            # even if the SMTP server is down.
            try:
                data_dict = {
                    "full_name": full_name,
                    "email": email,
                    "dropoff_date": dropoff_date,
                    "fridge_name": fridge_name,
                    "quantity": quantity,
                    "item_name": item_name,
                    "notes": notes
                }
               
                msg = Message(
                    subject=f"Donation Confirmation: {item_name}",
                    recipients=[email]
                )
                # Ensure these templates exist in your /templates/email/ folder
                msg.body = render_template('email/emailtext.txt', **data_dict)
                msg.html = render_template('email/emaildropoff.html.jinja', **data_dict)
                
                mail.send(msg)
            except Exception as email_err:
                # Log the error, but don't stop the redirect
                print(f"Mail failed to send: {email_err}")
                flash("Donation saved, but we couldn't send the confirmation email.", "donation_error")

            # Final Success Redirect
            return redirect(url_for("thank"))

        except Exception as e:
            connection.rollback()
            print(f"Critical Database Error: {e}")
            flash("A technical error occurred saving your donation. Please try again.", "donation_error")
            return redirect(url_for("donations"))
        finally:
            connection.close()

    # --- GET SECTION (Same as your original) ---
    try:
        cursor.execute("SELECT ID, Name, Image FROM Fridge")
        fridges_data = cursor.fetchall()
        cursor.execute("SELECT ID, Name FROM Items")
        food_types_data = cursor.fetchall()
        
        return render_template(
            "donateinfo.html.jinja",
            fridges=fridges_data,
            food_types=food_types_data
        )
    finally:
        connection.close()

@app.route('/donation/<int:id>/delete', methods=["POST"])
@login_required
def delete_donation(id):
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM Donations
        WHERE ID = %s AND UserID = %s
    """, (id, current_user.id))

    connection.commit() 
    connection.close()

    flash("Donation deleted")
    return redirect('/restaurant-dashboard')

# -----------------------
# PERSONAL FRIDGES
# -----------------------
@app.route("/individfridge/<int:fridge_id>", methods=["GET", "POST"])
def personal_fridges(fridge_id):
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # --- 1. HANDLE POST (Review Submission) ---
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("You must be logged in to leave a review.", "error")
            return redirect(url_for("login"))

        rating = request.form.get("Rating")
        comment = request.form.get("Comment")
        
        if rating and comment:
            cursor.execute("SELECT ID FROM Reviews WHERE FridgeID = %s AND UserID = %s", (fridge_id, current_user.id))
            existing_review = cursor.fetchone()

            if existing_review:
                flash("You've already reviewed this fridge! Please edit your existing message below.", "review-exists")
            else:
                try:
                    cursor.execute("""
                        INSERT INTO Reviews (FridgeID, rating, comment, UserID, Timestamp) 
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (fridge_id, rating, comment, current_user.id))
                    connection.commit()
                    flash("Review submitted! Thank you for sharing.", "review-success")
                except Exception as e:
                    print(f"Database Error: {e}")
                    flash("An error occurred. Please try again later.", "error")
            
            connection.close()
            return redirect(url_for("personal_fridges", fridge_id=fridge_id))

    # --- 2. HANDLE GET (Page Display) ---
    # Fetch Fridge Info
    cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))
    fridge = cursor.fetchone()

    if not fridge:
        connection.close()
        abort(404)

    # ⭐ NEW: Check if this fridge is favorited by the current user
    is_favorited = False
    if current_user.is_authenticated:
        cursor.execute(
            "SELECT 1 FROM Favorites WHERE UserID = %s AND FridgeID = %s",
            (current_user.id, fridge_id)
        )
        is_favorited = cursor.fetchone() is not None

    # Fetch Inventory
    cursor.execute("""
        SELECT i.Name, i.Image, fi.Quantity 
        FROM Fridge_items fi
        JOIN Items i ON fi.ItemsID = i.ID 
        WHERE fi.FridgeID = %s AND fi.Quantity > 0
    """, (fridge_id,))
    items_list = cursor.fetchall()

    # Fetch Status
    cursor.execute("""
    SELECT *
    FROM Fridge_status
    WHERE FridgeID = %s
    ORDER BY Last_updated DESC
    LIMIT 1
""", (fridge_id,))
    fridge_status = cursor.fetchone() or {"Status": "Unknown", "Last_updated": None}

    # Fetch Reviews
    cursor.execute("""
        SELECT r.ID AS ReviewID, r.rating AS Rating, r.comment AS Comment, r.Timestamp, u.Name AS user_name, r.UserID 
        FROM Reviews r 
        JOIN User u ON r.UserID = u.ID 
        WHERE r.FridgeID = %s 
        ORDER BY r.Timestamp DESC
    """, (fridge_id,))
    reviews = cursor.fetchall()

    connection.close()
    
    # Send is_favorited to the template
    return render_template(
        "fridge.html.jinja", 
        fridge=fridge, 
        items=items_list, 
        reviews=reviews, 
        fridge_status=fridge_status,
        is_favorited=is_favorited
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
            "status": row["status"] if row["status"] else "Unknown"
        })


   return jsonify(fridges)


# -----------------------
# REPORT FRIDGE ISSUE
# -----------------------
@app.route("/report/<int:fridge_id>", methods=["GET", "POST"])
@login_required
def report_fridge(fridge_id):
    if request.method == "POST":
        priority = request.form.get("priority")
        reproducibility = request.form.get("reproducibility")
        description = request.form.get("issue_description")
        
        connection = connect_db()
        try:
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            
            # 1. Verify fridge exists and get details for the email
            cursor.execute("SELECT Name, Address FROM Fridge WHERE ID=%s", (fridge_id,))
            fridge = cursor.fetchone()

            if not fridge:
                flash("Fridge not found.", "error")
                return redirect(url_for("index"))

            # 2. Log the maintenance report
            # Note: Ensure these columns match your 'maintenance_reports' table exactly
            cursor.execute("""
                INSERT INTO maintenance_reports
                (FridgeID, Reported_by, Description, Status, Timestamp, UserID, Priority, Reproducibility)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
            """, (fridge_id, current_user.id, description, "Open", current_user.id, priority, reproducibility))

            # 3. UPDATE FRIDGE STATUS
            # Update the main Fridge table so it shows up as Needs Attention globally
        
            
            # 4. INSERT INTO STATUS HISTORY
            # This ensures the 'Last Sync' info on the fridge page shows the update
            cursor.execute("""
                INSERT INTO Fridge_status (FridgeID, Status, Last_updated)
                VALUES (%s, %s, NOW())
            """, (fridge_id, "Needs Attention"))
            
            # Commit all database changes
            connection.commit()

            # 5. Notify via Email
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            email_body = f"""
            --------------------------------------------------
            MAINTENANCE ALERT: {fridge['Name']}
            --------------------------------------------------
            STATUS CHANGE: Needs Attention
            PRIORITY:      {priority.upper()}
            TIMESTAMP:     {timestamp}

            ISSUE DETAILS:
            {description}

            REPORTED BY: {current_user.name} ({current_user.email})
            --------------------------------------------------
            """

            msg = MIMEText(email_body)
            msg['Subject'] = f"🚨 [{priority.upper()}] Maintenance Report - {fridge['Name']}"
            msg['From'] = app.config['MAIL_USERNAME']
            msg['To'] = "fridge.net5@gmail.com"

            with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
                server.starttls()
                server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                server.send_message(msg)

            flash("Report submitted. This fridge has been marked as 'Needs Attention'.", "success")
            
            # REDIRECT: Returns user to the individual fridge page
            return redirect(url_for("personal_fridges", fridge_id=fridge_id))

        except Exception as e:
            if connection:
                connection.rollback()
            print(f"Error: {e}")
            flash("Failed to submit report. Please try again.")
        finally:
            connection.close()

    # --- GET logic for displaying the form ---
    connection = connect_db()
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))
        fridge = cursor.fetchone()
    finally:
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
            fridge_status=status
        )

    # -------- POST --------
    # -------- POST --------
    # 1. Define fullness mapping
    value = int(request.form.get("fullness", 2))
    mapping = ["empty", "few", "half", "many", "full"]
    status_value = mapping[value]
    
    # 2. Define is_broken from the form
    # Make sure your HTML checkbox has name="is_broken"
    is_broken = request.form.get("is_broken") == "on"

    # 3. Process item quantities
    for key in request.form:
        if key.startswith("quantity_"):
            try:
                item_id = int(key.split("_")[1])
                quantity = int(request.form[key])

                if quantity <= 0:
                    cursor.execute(
                        "DELETE FROM Fridge_items WHERE FridgeID=%s AND ItemsID=%s",
                        (fridge_id, item_id)
                    )
                else:
                    cursor.execute("""
                        INSERT INTO Fridge_items (FridgeID, ItemsID, Quantity)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE Quantity = VALUES(Quantity)
                    """, (fridge_id, item_id, quantity))
            except (ValueError, IndexError):
                continue

    # 4. Update Status (Only in Fridge_status table)
    current_time = datetime.now(timezone.utc)

    if is_broken:
        final_status = "Needs Attention"
        flash("Quantities updated, but status marked as 'Needs Attention'.", "fridge_error")
    else:
        final_status = status_value
        flash("Fridge updated successfully!", "fridge_success")

    # This table exists, so we insert here
    cursor.execute("""
        INSERT INTO Fridge_status (FridgeID, Status, Last_updated)
        VALUES (%s, %s, %s)
    """, (fridge_id, final_status, current_time))

    connection.commit()
    connection.close()

    # Ensure this route name is correct in your app
    return redirect(url_for("personal_fridges", fridge_id=fridge_id))

# -----------------------
# PROFILE PAGE
# -----------------------
@app.route("/profile_page")
@login_required
def account():
   return render_template("components/profile.html.jinja")

# PROFILE USERNAME
@app.route("/profile/update-username", methods=["POST"])
@login_required
def update_username():
   username = request.form.get("username", "").strip()
   if not username:
       flash("Username cannot be empty", "profile_error")
       return redirect("/profile")
   connection = connect_db()
   cursor = connection.cursor()
   cursor.execute("UPDATE User SET Name = %s WHERE ID = %s", (username, current_user.id))
   connection.close()
   current_user.name = username
   flash("Username updated!", "profile_success")
   return redirect("/profile_page")



# PROFILE PASSWORD 
@app.route("/profile/update-password", methods=["POST"])
@login_required
def update_password():
   password = request.form.get("password", "")
   if len(password) < 8:
    flash("Password must be at least 8 characters", "profile_error")
    return redirect("/profile")
   connection = connect_db()
   cursor = connection.cursor()
   cursor.execute("UPDATE User SET Password = %s WHERE ID = %s", (password, current_user.id))
   connection.close()
   flash("Password updated!", "profile_success")
   return redirect("/profile_page")


# PROFILE PICTURE 
@app.route("/profile/update-picture", methods=["POST"])
@login_required
def update_picture():

    picture_url = request.form.get("picture_url", "").strip()

    # Validate URL
    if picture_url and not picture_url.startswith(("https://", "/static/")):
        flash(
            "Invalid image URL. Use https:// or /static/ path.",
            "profile_error"
        )
        return redirect("/profile_page")

    connection = connect_db()

    try:
        cursor = connection.cursor()

        # Update database
        cursor.execute(
            "UPDATE User SET ProfilePicture = %s WHERE ID = %s",
            (picture_url if picture_url else None, current_user.id)
        )

        # Save changes
        connection.commit()

        # Update current user immediately
        current_user.profile_picture = (
            picture_url if picture_url else None
        )

        flash("Profile picture updated!", "profile_success")

    except Exception as e:
        print(f"Error: {e}")
        flash(
            "Database error. Please try again.",
            "profile_error"
        )

    finally:
        connection.close()

    return redirect("/profile_page")

# DELETE ACCOUNT
@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    connection = connect_db()
    cursor = connection.cursor()
    
    try:
        user_id = current_user.id
        
        # 1. DELETE EVERYTHING CONNECTED TO THE USER FIRST
        cursor.execute("DELETE FROM Reviews WHERE UserID = %s", (user_id,))
        cursor.execute("DELETE FROM Favorites WHERE UserID = %s", (user_id,))
        
        # 2. NOW DELETE THE USER
        cursor.execute("DELETE FROM User WHERE ID = %s", (user_id,))
        
        connection.commit()
        
        # 3. CLEAR SESSION
        logout_user()
        flash("Account deleted successfully.", "info")
        return redirect(url_for("index"))
        
    except Exception as e:
        print(f"DATABASE ERROR: {e}") # Check your terminal for this output!
        connection.rollback()
        flash("Could not delete account. System error.", "error")
        return redirect(url_for("account"))
    finally:
        cursor.close()
        connection.close()


# -----------------------
# ABOUT PAGE
# -----------------------
@app.route("/about")
def about():
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)  

   
    # TOTAL USERS
    cursor.execute("SELECT COUNT(*) AS total_users FROM User")
    users = cursor.fetchone()["total_users"]

 
    # TOTAL FRIDGES
    cursor.execute("SELECT COUNT(*) AS total_fridges FROM Fridge")
    fridges = cursor.fetchone()["total_fridges"]

    
    # TOTAL DONATIONS
    cursor.execute("SELECT COUNT(*) AS total_donations FROM Donations")
    meals = cursor.fetchone()["total_donations"]

    # FOOD DONATIONS
    cursor.execute("""
        SELECT COALESCE(SUM(Quantity), 0) AS total_food
        FROM Donations
        WHERE Type = 'food'
    """)
    food_saved = cursor.fetchone()["total_food"]

    
    # MONEY DONATIONS
    cursor.execute("""
        SELECT COALESCE(SUM(Quantity), 0) AS total_money
        FROM Donations
        WHERE Type = 'money'
    """)
    money = cursor.fetchone()["total_money"]

    if user_lat and user_lng:
        # Distance-aware query (10-mile radius)
        fow_query = """
            SELECT f.*, COUNT(fs.ID) as activity_count,
            (3959 * acos(cos(radians(%s)) * cos(radians(f.Latitude)) * cos(radians(f.Longitude) - radians(%s)) + sin(radians(%s)) * sin(radians(f.Latitude)))) AS distance
            FROM Fridge f
            LEFT JOIN Fridge_status fs ON f.ID = fs.FridgeID
            WHERE fs.Last_updated >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY f.ID
            HAVING distance < 10
            ORDER BY activity_count DESC, distance ASC
            LIMIT 1
        """
        cursor.execute(fow_query, (user_lat, user_lng, user_lat))
    else:
        # Fallback: Just the most active fridge globally
        fow_query = """
            SELECT f.*, COUNT(fs.ID) as activity_count
            FROM Fridge f
            JOIN Fridge_status fs ON f.ID = fs.FridgeID
            WHERE fs.Last_updated >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY f.ID
            ORDER BY activity_count DESC
            LIMIT 1
        """
        cursor.execute(fow_query)
    
    fridge_of_week = cursor.fetchone()
    connection.close()

    stats = {
        "meals": meals,
        "users": users,
        "fridges": fridges,
        "food_saved": food_saved,
        "money": money
    }

    return render_template("aboutus.html.jinja", stats=stats, fow=fridge_of_week)

# -----------------------
# STATISTICS PAGE 
# -----------------------
@app.route("/api/stats")
def api_stats():
   connection = connect_db()
   cursor = connection.cursor(pymysql.cursors.DictCursor)

   cursor.execute("SELECT COUNT(*) AS total_users FROM User")
   users = cursor.fetchone()["total_users"]

   cursor.execute("SELECT COUNT(*) AS total_fridges FROM Fridge")
   fridges = cursor.fetchone()["total_fridges"]

   cursor.execute("SELECT COUNT(*) AS total_donations FROM Donations")
   meals = cursor.fetchone()["total_donations"]

   cursor.execute("SELECT COALESCE(SUM(Quantity),0) AS total_food FROM Donations WHERE Type='food'")
   food_saved = cursor.fetchone()["total_food"]

   cursor.execute("SELECT COALESCE(SUM(Quantity),0) AS total_money FROM Donations WHERE Type='money'")
   money = cursor.fetchone()["total_money"]

   connection.close()

   return jsonify({
       "users": users,
       "fridges": fridges,
       "meals": meals,
       "food_saved": food_saved,
       "money": money
   })


# -----------------------
# FAVORITES
# -----------------------
@app.route('/toggle-favorite', methods=['POST'])
def toggle_favorite():
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401
    connection = None
    try:
        data = request.get_json()
        fridge_id = int(data.get('fridge_id'))
        user_id = current_user.id

        connection = connect_db()
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        cursor.execute(
            "SELECT * FROM Favorites WHERE UserID = %s AND FridgeID = %s",
            (user_id, fridge_id)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "DELETE FROM Favorites WHERE UserID = %s AND FridgeID = %s",
                (user_id, fridge_id)
            )
            message = "Removed from favorites"
            action = "removed"
        else:
            cursor.execute(
                "INSERT INTO Favorites (UserID, FridgeID) VALUES (%s, %s)",
                (user_id, fridge_id)
            )
            message = "Added to favorites"
            action = "added"

        connection.commit()

        return jsonify({
            "success": True,
            "message": message,
            "action": action
        })

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"ERROR IN TOGGLE: {e}")

        return jsonify({
            "success": False,
            "message": "Something went wrong"
        }), 500

    finally:
        if connection:
            connection.close()

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

        # 1. Validation
        if not name or not email or not message:
            flash("Please fill out all fields.", "danger")
            return redirect(url_for("contact"))

        # 2. Email Notification to Admin
        try:
            msg = Message(
                subject=f"New Contact Form Submission from {name}",
                sender=app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=['fridge.net5@gmail.com'], # Your admin email
                body=f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
            )
            mail.send(msg)
            flash("Your message has been sent! We will get back to you soon.", "success")
        except Exception as e:
            print(f"Mail error: {e}")
            flash("There was an error sending your message. Please try again later.", "danger")

        return redirect(url_for("contact"))

    return render_template("contact.html.jinja")


# --------------------
 # RESTAURANTS CONNECT PAGE 
# --------------------
@app.route("/restaurants-connect", methods=["GET", "POST"])
def restaurants_connect():
    connection = connect_db()
    # dictionary=True allows us to access data like fridge['name'] in Jinja
    cursor = connection.cursor()

    try:
        if request.method == "POST":
            # Form Submission Logic
            name = request.form["restaurant_name"]
            contact = request.form["contact_person"]
            email = request.form["email"]
            phone = request.form["phone"]
            address = request.form["address"]
            food_type = request.form["food_type"]
            delivery = request.form["delivery_method"]

            cursor.execute("""
                INSERT INTO restaurant_partners 
                (Name, Spokesperson, Email, Phone, Address, Food_type, Delivery_method)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, contact, email, phone, address, food_type, delivery))
            
            connection.commit()
            return redirect("/thank_you")

        # --- GET DATA FOR LIVE UI ---
        
        # 1. Fetch latest fridge statuses 
        cursor.execute("""
            SELECT f.ID, f.name, fs.Status, fs.Last_updated 
            FROM Fridge f
            JOIN Fridge_status fs ON f.ID = fs.FridgeID
            WHERE fs.Last_updated = (
                SELECT MAX(Last_updated) 
                FROM Fridge_status 
                WHERE FridgeID = f.ID
            )
        """)
        fridges_data = cursor.fetchall()

        # 2. Fetch total maintenance count
        cursor.execute("SELECT COUNT(*) as count FROM maintenance_reports WHERE Status != 'Resolved'")
        maint_res = cursor.fetchone()
        maint_count = maint_res['count'] if maint_res else 0

        # 3. Check for any High Priority maintenance issues
        cursor.execute("SELECT COUNT(*) as high FROM maintenance_reports WHERE Priority = 'High' AND Status != 'Resolved'")
        high_priority = cursor.fetchone()['high']

    finally:
        cursor.close()
        connection.close()

    return render_template("restaurant_connect.html.jinja", 
                           fridges=fridges_data, 
                           maint_count=maint_count,
                           urgent=high_priority)


# ------------------------------
# DASHBOARD
# ------------------------------
@app.route("/restaurant-dashboard")
@login_required
def restaurant_dashboard():
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    try:
        # 1. IMPACT METRICS (Food and Money)
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN Type = 'food' THEN Quantity ELSE 0 END) AS total_meals,
                SUM(CASE WHEN Type = 'money' THEN Quantity ELSE 0 END) AS total_money
            FROM Donations
            WHERE UserID = %s
        """, (current_user.id,))
        stats = cursor.fetchone()
        total_meals = stats["total_meals"] or 0
        total_money = stats["total_money"] or 0

        # 2. UPCOMING PICKUPS (Future or Today)
        cursor.execute("""
            SELECT ID, Quantity, Dropoff
            FROM Donations
            WHERE UserID = %s 
            AND Type = 'food'
            AND Dropoff >= NOW()
            ORDER BY Dropoff ASC
        """, (current_user.id,))
        scheduled_list = cursor.fetchall()
        scheduled_count = len(scheduled_list)

        # 3. PREVIOUS DROPOFFS (Past)
        cursor.execute("""
            SELECT ID, Quantity, Dropoff
            FROM Donations
            WHERE UserID = %s 
            AND Type = 'food'
            AND Dropoff < NOW()
            ORDER BY Dropoff DESC
            LIMIT 10
        """, (current_user.id,))
        previous_list = cursor.fetchall()

    finally:
        connection.close()

    return render_template(
        "restaurant_dashboard.html.jinja",
        total_meals=total_meals,
        total_money=total_money,
        scheduled=scheduled_count,
        scheduled_list=scheduled_list,
        previous_list=previous_list
    )

# ------------------------------
# DONATIONS DETAILS (DASHBOARD)
# ------------------------------
@app.route("/api/donation-details/<int:donation_id>")
@login_required
def donation_details(donation_id):
        connection = connect_db()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get donation details + Fridge Name + Item Name/Image
        query = """
            SELECT d.*, f.Name as FridgeName, i.Name as ItemName, i.Image as ItemImage
            FROM Donations d
            JOIN Fridge f ON d.FridgeID = f.ID
            LEFT JOIN Items i ON d.FoodCategory = i.ID
            WHERE d.ID = %s AND d.UserID = %s
        """
        cursor.execute(query, (donation_id, current_user.id))
        donation = cursor.fetchone()
        connection.close()
        
        if not donation:
            return jsonify({"error": "Donation not found"}), 404
            
        # Format the date for the JavaScript display
        if donation ['Dropoff']:
            donation['FormattedDate'] = donation['Dropoff'].strftime('%B %d, %Y')
            donation['FormattedTime'] = donation['Dropoff'].strftime('%I:%M %p')
        
        return jsonify({
        "ItemName": donation['ItemName'],
        "Quantity": donation['Quantity'],
        "FridgeName": donation['FridgeName'],
        "Notes": donation['Notes'],
        "ItemImage": donation['ItemImage'],
        # Formatting the time accurately for the frontend
        "FormattedDate": donation['Dropoff'].strftime('%B %d, %Y'),
        "FormattedTime": donation['Dropoff'].strftime('%I:%M %p'),
        "Dropoff": donation['Dropoff'].isoformat() # Fallback for JS Date()
    })
    

# --------------------
# EDIT REVIEW 
# --------------------
@app.route("/edit-review/<int:review_id>", methods=["POST"])
@login_required
def edit_review(review_id):
    new_comment = request.form.get("Comment")
    new_rating = request.form.get("Rating") # Pull the rating from the radio buttons

    connection = connect_db()
    cursor = connection.cursor()

    # Ensure the user actually owns the review they are trying to edit
    cursor.execute("""
        UPDATE Reviews 
        SET comment = %s, rating = %s, Timestamp = NOW() 
        WHERE ID = %s AND UserID = %s
    """, (new_comment, new_rating, review_id, current_user.id))
    
    connection.commit()
    connection.close()

    flash("Review updated successfully!", "success")
    # Redirect back to the previous page
    return redirect(request.referrer)

# --------------------
# VIEW ALL REVIEWS 
# --------------------
@app.route("/fridge/<int:fridge_id>/reviews")
def all_reviews(fridge_id):
    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    
    # Get Fridge Name for the heading
    cursor.execute("SELECT Name FROM Fridge WHERE ID=%s", (fridge_id,))
    fridge = cursor.fetchone()
    
    if not fridge:
        abort(404)

    # Get All Reviews
    cursor.execute("""
        SELECT r.rating AS Rating, r.comment AS Comment, r.Timestamp, u.Name AS user_name 
        FROM Reviews r 
        JOIN User u ON r.UserID = u.ID 
        WHERE r.FridgeID = %s 
        ORDER BY r.Timestamp DESC
    """, (fridge_id,))
    all_reviews = cursor.fetchall()
    
    connection.close()
    return render_template("all_reviews.html.jinja", reviews=all_reviews, fridge=fridge)

@app.route("/forgot_password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():

    if request.method == "POST":

        email = request.form["email"].strip().lower()

        connection = None
        cursor = None

        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT * FROM User WHERE Email = %s",
                (email,)
            )

            user = cursor.fetchone()

            # ONLY if account exists
            if user:

                token = secrets.token_urlsafe(32)
                token_hash = hash_token(token)

                expiry = datetime.now() + timedelta(hours=1)

                cursor.execute("""
                    UPDATE User
                    SET ResetToken = %s,
                        ResetTokenExpiry = %s
                    WHERE Email = %s
                """, (token_hash, expiry, email))

                connection.commit()

                reset_link = url_for(
                    "reset_password",
                    token=token,
                    _external=True
                )

                send_email(
                    subject="Reset Your Password",
                    recipients=[email],
                    template_txt="email/reset.txt",
                    template_html="email/reset.html.jinja",
                    context={
                        "name": user["Name"],
                        "reset_link": reset_link
                    }
                )

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

        flash(
            "If an account exists, a reset link has been sent.",
            "success"
        )

        return redirect("/login")

    return render_template("forgot_password.html.jinja")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password(token):

    connection = None
    cursor = None

    try:
        connection = connect_db()

        # IMPORTANT:
        # Use dictionary=True if you're using user["ColumnName"]
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Hash incoming token from URL
        hashed_token = hash_token(token)

        # Find matching token
        cursor.execute("""
            SELECT *
            FROM User
            WHERE ResetToken = %s
        """, (hashed_token,))

        user = cursor.fetchone()

        # Invalid token
        if not user:
            flash("Invalid or expired reset link.", "error")
            return redirect("/forgot_password")

        # Expired token
        if datetime.now() > user["ResetTokenExpiry"]:
            flash("Reset link has expired.", "error")
            return redirect("/forgot_password")

        # FORM SUBMIT
        if request.method == "POST":

            password = request.form["password"]
            confirm_password = request.form["confirm_password"]

            # Password mismatch
            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template(
                    "password_reset.html.jinja"
                )

            # Password too short
            if len(password) < 8:
                flash(
                    "Password must be at least 8 characters.",
                    "error"
                )
                return render_template(
                    "password_reset.html.jinja"
                )

            # Hash new password
            hashed_password = generate_password_hash(password)

            # Update password + clear token
            cursor.execute("""
                UPDATE User
                SET Password = %s,
                    ResetToken = NULL,
                    ResetTokenExpiry = NULL
                WHERE ID = %s
            """, (hashed_password, user["ID"]))

            connection.commit()

            flash(
                "Password reset successfully. Please log in.",
                "success"
            )

            return redirect("/login")

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return render_template("password_reset.html.jinja")



# --------------------
# NAME IF STATEMENT 
# --------------------
if __name__ == "__main__":
   app.run(debug=True)

