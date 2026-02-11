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


@app.route("/donations")
def donate():
     return render_template("donations.html.jinja")

@app.route("/type_donate")
def type_donate():
     return render_template("donateinfo.html.jinja")
