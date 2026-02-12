from flask import Flask, render_template, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
import pymysql

from dynaconf import Dynaconf

from flask import request, redirect, url_for, render_template
app = Flask(__name__)

config = Dynaconf(settings_file=["settings.toml"])
 

login_manager = LoginManager(app)
login_manager.login_view = '/login'

class User:
    is_authenticated = True
    is_active = True
    is_annoymous = False 

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
        password=config.password,
        database="fridge_net",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

    return conn

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

@app.route("/")
def index():
    return render_template("homepage.html.jinja")

@app.route("/map")
def map():
     return render_template("map.html.jinja")

@app.route("/report")
def report():
    return render_template("report.html.jinja")


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
                    INSERT INTO `User` (`Name`, `Password`, `Email`, `Address`)
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
    return render_template("donations.html.jinja")

@app.route("/donate")
def donate():
     return render_template("donate.html.jinja")

@app.route("/type_donate")
def type_donate():
     return render_template("donateinfo.html.jinja")

@app.route("/donate-money", methods=["POST"])
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
def donate_food():
    name = request.form.get("food_name")
    date = request.form.get("dropoff_date")

    print(f"Food Donation scheduled by {name} on {date}")

    flash("Your food drop-off has been scheduled!")
    return redirect ("type_donate")

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/fridge")
def fridge():
    return render_template ("fridge.html.jinja")
