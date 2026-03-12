from flask import Flask, render_template, request, flash, abort, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
import pymysql
import random
from dynaconf import Dynaconf

app = Flask(__name__)

config = Dynaconf(settings_file=["settings.toml"])
app.secret_key = config.secret_key

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
        password=config.PASSWORD,
        database="fridge_net",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

# -----------------------
# ERROR HANDLER
# -----------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html.jinja"), 404

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
@app.route("/donate")
@login_required
def donate():
    return render_template("donate.html.jinja")

@app.route("/type_donate")
@login_required
def type_donate():
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM `Items`")
    items = cursor.fetchall()
    connection.close()
    return render_template("donateinfo.html.jinja", items=items)

@app.route("/donate-money", methods=["POST"])
@login_required
def donate_money():
    amount = request.form.get("amount")
    custom_amount = request.form.get("custom_amount")
    name = request.form.get("name")
    final_amount = custom_amount if custom_amount else amount
    flash("Thank you for your monetary donation!")
    return redirect("type_donate")

@app.route("/donate-food", methods=["POST"])
@login_required
def donate_food():
    name = request.form.get("food_name")
    date = request.form.get("dropoff_date")
    flash("Your food drop-off has been scheduled!")
    return redirect("type_donate")

# -----------------------
# INDIVIDUAL FRIDGE PAGE
# -----------------------
@app.route("/individfridge/<int:fridge_id>", methods=["GET","POST"])
def personal_fridges(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()

    if request.method == "POST":
        rating = request.form["Rating"]
        comment = request.form["Comment"]
        user_id = current_user.id if current_user.is_authenticated else None
        if not user_id:
            return "You must be logged in to review", 400
        cursor.execute("INSERT INTO Reviews (FridgeID, rating, comment, UserID) VALUES (%s,%s,%s,%s)",
                       (fridge_id, rating, comment, user_id))
        connection.commit()
        return redirect(url_for("personal_fridges", fridge_id=fridge_id))

    cursor.execute("SELECT * FROM Fridge WHERE ID=%s", (fridge_id,))
    fridge = cursor.fetchone()
    cursor.execute("SELECT * FROM Reviews WHERE FridgeID=%s", (fridge_id,))
    reviews = cursor.fetchall()
    connection.close()

    if not fridge:
        abort(404)

    return render_template("fridge.html.jinja", fridge=fridge, reviews=reviews)

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
def thank():
    return render_template("components/thanks.html.jinja")

# -----------------------
# UPDATE FRIDGE STATUS
# -----------------------
@app.route("/update/<fridge_id>")
def update(fridge_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE Fridge_status fs
        JOIN (
            SELECT FridgeID, MAX(Last_updated) AS max_time
            FROM Fridge_status
            GROUP BY FridgeID
        ) latest ON fs.FridgeID = latest.FridgeID AND fs.Last_updated = latest.max_time
        SET fs.Status = 'Updated'
        WHERE fs.FridgeID=%s
    """, (fridge_id,))
    connection.commit()
    connection.close()
    return render_template("update_fridge.html.jinja")

# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)