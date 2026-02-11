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
        database="smack_prime_kicks",
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
def donate():
     return render_template("map.html.jinja")


@app.route("/donate")
def donate():
     return render_template("donate.html.jinja")


@app.route("/report")
def index():
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
        name=request.form["name"]
        email=request.form["email"]
        password=request.form["password"]
        password_repeat=request.form["repeat_password"]
        address=request.form["address"]
        birthdate=request.form["birthdate"]
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