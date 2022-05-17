import os
import requests

from flask import Flask, session, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from tempfile import gettempdir
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from helpers import *

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
##@login_required
def index():
    #redirect to search
    return redirect("/search")
    
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        user = request.form.get("user")

        if not "user":
            return apology("must provide username")

        # ensure password was submitted
        password = request.form.get("pass")

        if not "password":
            return apology("must provide password")

        # query database for username
        login = db.execute("SELECT * FROM users WHERE username = :username AND password = :pass", 
        {"username": user, "pass": password}).fetchone()
		
        if not login:
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = login.id

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        user = request.form.get("username")

        if not user:
            return apology("must provide username")

        # ensure password was submitted
        password = request.form.get("password")

        if not password:
            return apology("must provide password")

        # ensure password and verified password is the same
        ##elif password != request.form.get("passwordagain"):
        ##    return apology("password doesn't match")

        register = db.execute("SELECT * FROM users WHERE username = :username",{"username": user}).fetchone()

        # checks if the username is not already taken
        if register:
            return apology("Username already exists")
        
        # insert the new user into users, encrypting and storing that user's password
        db.execute("INSERT INTO users (username, password) VALUES( :username, :password )", {"username": user, "password": password})

        db.commit()

        registered = db.execute("SELECT id FROM users WHERE username = :username AND password = :password", \
             {"username": user, "password": password}).fetchone()

        # store the registered user
        session["user_id"] = registered.id

        # redirect user to home page
        return redirect(url_for("index"))

    else:
        return render_template("register.html")

@app.route("/search",methods = ["GET","POST"])
@login_required
def search():
    if request.method == "POST":


        #look for isbn, title and author of book
        input = "%"+ request.form.get("input") + "%"

        books = db.execute("SELECT * FROM books WHERE isbn LIKE :input OR author LIKE :input OR title LIKE :input"
            , {"input": input}).fetchall()

        # if no books are found
        if not books:
            return apology("No Books found")
        return render_template("found.html", books = books)
    
    elif request.method == "GET":
        return render_template("search.html")

@app.route("/search/<string:isbn>", methods=["GET", "POST"])
@login_required
def bookpage(isbn):

    # get rating info on books    
    isbn = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn":isbn}).fetchone()

    res = requests.get("https://www.goodreads.com/book/review_counts.json", 
        params={"key": "3B3ESC4uAuaby9bVpXfLw", "isbns": isbn.isbn})
    data = res.json()

    ## create rating variables
    avg = data["books"][0]["average_rating"] 
    count = data["books"][0]["work_ratings_count"]

    if request.method == "POST":
        rating = request.form.get("rating")
        review = request.form.get("review")

        # add review to database
        db.execute("INSERT INTO reviews (id, isbn, rating, review) VALUES (:idd, :isbn, :rating, :review)" 
        , {"idd": session["user_id"] ,"isbn": isbn.isbn, "rating": rating, "review": review})
        db.commit()

    elif request.method == "GET":

        # if arriving from searcher
        review = db.execute("SELECT * FROM reviews WHERE isbn = :isbn AND id = :idd"
            , { "isbn": isbn.isbn, "idd": session["user_id"]}).fetchone()

        # if no review in the database for this book
        if not review:
            return render_template("bookpage.html", isbn=isbn, avg=avg , count=count, reviewed=False)
        
        # if there is a review in the database for this book
        else:
            rating = review.rating
            review = review.review
    
    return render_template("bookpage.html", isbn=isbn, avg=avg , count=count, reviewed=True, rating=rating, review=review)

@app.route("/api/<string:isbn>", methods=["GET", "POST"])
def api(isbn):
    ## get info from books
    info = db.execute("SELECT * FROM books WHERE isbn=:isbn",{'isbn':isbn}).fetchone()
    
    # count rating and average it
    count = db.execute("SELECT COUNT(rating) AS count FROM reviews WHERE isbn=:isbn",{'isbn':isbn}).fetchone()
    average = db.execute("SELECT AVG(rating) AS average FROM reviews WHERE isbn= :isbn",{'isbn':isbn}).fetchone()[0]
    print(average)
    average = float(average)
    
    # send new data to api link
    data = {"title": info.title, "author": info.author, "year": info.year,"isbn":isbn, "average rating": average, "review_count":count.count}
    return jsonify(data)