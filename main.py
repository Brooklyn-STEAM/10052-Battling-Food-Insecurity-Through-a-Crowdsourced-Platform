from flask import Flask, render_template, request, flash, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
import pymysql 

from dynaconf import Dynaconf

from flask import request, redirect, url_for, render_template
app = Flask(__name__)
app.secret_key = "your"
config = Dynaconf(settings_file=["settings.toml"])

app.secret_key = config.secret_key

login_manager = LoginManager(app)

login_manager.login_view = '/login'



class User:
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, result):
        self.name = result['Name']
        self.email = result['Email']
        self.address = result['Address']
        self.id = result['ID']

    def get_id(self):
        return str(self.id)
    
def connect_db():
    conn = pymysql.connect(
        host="db.steamcenter.tech", 
        user="smack",
        password=config.PASSWORD,
        database="fridge_net",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

    return conn

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html.jinja"),404

@login_manager.user_loader
def load_user(user_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM `User` WHERE `ID` = %s ", (user_id) )
    result = cursor.fetchone()
    connection.close()

    if result is None:  
        return None
    
    return User(result)

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/")
def index():
    return render_template("homepage.html.jinja")

@app.route("/map")
def map():
     return render_template("map.html.jinja")

@app.route("/report/<int:fridge_id>")
def report_fridge(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()
    # Fetch data for the specific fridge
    cursor.execute("SELECT * FROM Fridge WHERE ID = %s", (fridge_id,))
    fridge = cursor.fetchone()
    connection.close()

    if not fridge:
        abort(404)
        
    return render_template("report.html.jinja", fridge=fridge)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM `User` WHERE `Email` = %s AND `Password` = %s", (email, password) )
        result = cursor.fetchone()
        connection.close()

        if result is None:
            flash("Invalid email or password")
            return redirect(url_for("login"))
        
        user = User(result)
        login_user(user)

        return redirect(url_for("index"))

    return render_template("login.html.jinja")


@app.route("/logout", methods=['GET', 'POST'] )
@login_required
def logout():
    logout_user() # Logs out the current user
    flash("You have been logged out.") # Notify the user
    return redirect("/")


@app.route('/signup', methods=["POST", "GET"])# User Registration
def signup():
    # Handle POST request for user registration
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        password_repeat = request.form["repeat_password"]
        address = request.form["address"]
        # Validate password and confirmation
        if password != password_repeat:
            flash("Passwords do not match")
            # Redirect back to the signup page
        elif len(password) < 8:
         flash("Password must be at least 8 characters long") 
         # Redirect back to the signup page    
        else:
            connection = connect_db()
            
            cursor = connection.cursor()
            # Insert new user into the database
            try:
                cursor.execute("""
                    INSERT INTO `User` (`Name`, `Email` , `Password`, `Address`)
                    VALUES (%s, %s, %s, %s)
                """, (name, password, email, address))
                connection.close()
            # Handle duplicate email error
            except pymysql.err.IntegrityError:
                flash("User with that email already exists")
                connection.close()
            # If registration is successful, redirect to login page
            else:
                return redirect('/login')
        
        return render_template("signup.html.jinja")
    return render_template("signup.html.jinja")

@app.route("/donate")
@login_required
def donate():
     return render_template("donate.html.jinja")

@app.route("/product/<fridge_id>")
# Product page route
def product_page(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()
    # Execute query to get product by ID
    cursor.execute("SELECT * FROM `maintenance_reports` WHERE `ID` = %s", (fridge_id) )
                
    result = cursor.fetchall()
    
    connection.close()
    
    connection = connect_db()
    
    cursor = connection.cursor()
    # Execute query to get reviews for the product
    cursor.execute("""SELECT * FROM `Reviews` JOIN `User` ON `Reviews`.`UserID` = `User`.`ID` WHERE `FridgeID` = %s""", (fridge_id) )
    
    reviews = cursor.fetchall()
    
    connection.close()
    # If no product is found, redirect to dashboard
    if result is None: 
       return redirect("/dashboard") # If no product is found, return a 404 error
    
    return render_template("product.html.jinja", fridge = result , reviews=reviews)

@app.route("/type_donate")
@login_required
def type_donate():
     return render_template("donateinfo.html.jinja")

@app.route("/donate-money", methods=["POST"])
@login_required
def donate_money():
    amount = request.form.get("amount")
    custom_amount = request.form.get("custom_amount")
    name = request.form.get("name")

    final_amount = custom_amount if custom_amount else amount

    # Here you would integrate Stripe/PayPal
    print(f"Money Donation: {name} donated ${final_amount}")

    flash("Thank you for your monetary donation!")
    return redirect ("type_donate") 


@app.route("/donate-food", methods=["POST"])
@login_required
def donate_food():
    name = request.form.get("food_name")
    date = request.form.get("dropoff_date")

    print(f"Food Donation scheduled by {name} on {date}")

    flash("Your food drop-off has been scheduled!")
    return redirect ("type_donate")


@app.route("/individfridge/<fridge_id>")
def personal_fridges(fridge_id):
    # Connect to database
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT *
        FROM Fridge
        WHERE ID = %s
    """, (fridge_id,))
    fridge = cursor.fetchone()
    if not fridge:
        abort(404)
    cursor.execute("""
        SELECT r.*, u.Name as user_name
        FROM Reviews r
        JOIN User u ON r.UserID = u.ID
        WHERE r.FridgeID = %s
    """, (fridge_id,))
    reviews = cursor.fetchall()
    connection.close()
    
    # Return JSON
    return render_template("fridge.html.jinja", fridge=fridge, reviews=reviews)

@app.route("/get-fridges")
def get_fridges():
    connection = connect_db()
    cursor = connection.cursor()

    # Query to get all fridges with their latest status
    cursor.execute("""
        SELECT 
            f.ID AS id,
            f.Name AS name,
            f.Latitude AS lat,
            f.Longitude AS lng,
            (
                SELECT Status 
                FROM Fridge_status fs2
                WHERE fs2.FridgeID = f.ID
                ORDER BY Last_updated DESC
                LIMIT 1
            ) AS status
        FROM Fridge f;
    """)

    rows = cursor.fetchall()  # Fetch all results once
    connection.close()

    # Clean and parse data
    fridges = []
    for row in rows:
        try:
            lat = float(row['lat']) if row['lat'] is not None else None
            lng = float(row['lng']) if row['lng'] is not None else None
            if lat is None or lng is None:
                continue
            fridges.append({
                "id": row['id'],
                "name": row['name'].strip() if row['name'] else "Unnamed Fridge",
                "lat": lat,
                "lng": lng,
                "status": row['status'] if row['status'] else "Unknown"
            })
        except Exception as e:
            print(f"Skipping broken row: {row} ({e})")
            continue

    return jsonify(fridges)

@app.route("/thank_you")
def thank():
    return render_template("components/thanks.html.jinja")


@app.route("/report/<int:fridge_id>", methods=["GET", "POST"])
def reportfridge(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()

    if request.method == "POST":
        # 1. Collect form data
        priority = request.form.get("priority")
        reproducibility = request.form.get("reproducibility")
        description = request.form.get("issue_description")
        
        # 2. Get User Info
        u_id = current_user.id if current_user.is_authenticated else None
        now = datetime.now()

        # 3. Execute INSERT
        # Using UserID (no underscore) to match your row #7 in the screenshot
        cursor.execute("""
            INSERT INTO maintenance_reports 
            (FridgeID, Reported_by, Description, Status, Timestamp, UserID, Priority, Reproducibility)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (fridge_id, u_id, description, "Open", now, u_id, priority, reproducibility))
        
        connection.close()
        flash("Maintenance report submitted!")
        return redirect(url_for("index"))

    # GET logic: Display the form
    cursor.execute("SELECT * FROM Fridge WHERE ID = %s", (fridge_id,))
    fridge = cursor.fetchone()
    connection.close()

    if not fridge:
        abort(404)
        
    return render_template("report.html.jinja", fridge=fridge)


