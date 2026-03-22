from flask import Flask, render_template, request, redirect, session, url_for, send_file
import sqlite3
import os
import PyPDF2
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    best_match TEXT,
    score INTEGER,
    date TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------- JOB ROLES ----------------

job_roles = {

"Data Scientist":["python","machine learning","data analysis","pandas","numpy"],

"Web Developer":["html","css","javascript","flask","django"],

"Android Developer":["java","kotlin","android","xml"],

"Cyber Security":["networking","security","linux","cryptography"]

}


# ---------------- SUGGESTIONS ----------------

suggestions = {

"python":"Learn Python from online courses",
"machine learning":"Study ML basics and scikit-learn",
"pandas":"Practice data analysis using Pandas",
"django":"Build web apps using Django",
"javascript":"Learn DOM and modern JS frameworks",
"linux":"Practice Linux commands and networking"

}


# ---------------- PDF TEXT EXTRACTION ----------------

def extract_text_from_pdf(filepath):

    text=""

    with open(filepath,"rb") as file:

        reader=PyPDF2.PdfReader(file)

        for page in reader.pages:

            if page.extract_text():
                text+=page.extract_text()

    return text.lower()



# ---------------- HOME / DASHBOARD ----------------

@app.route("/")
def home():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")



# ---------------- REGISTER ----------------

@app.route("/register",methods=["GET","POST"])
def register():

    if request.method=="POST":

        username=request.form["username"]
        password=generate_password_hash(request.form["password"])

        try:

            conn=sqlite3.connect("users.db")
            cursor=conn.cursor()

            cursor.execute(
            "INSERT INTO users(username,password) VALUES (?,?)",
            (username,password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except:
            return "Username already exists"

    return render_template("register.html")



# ---------------- LOGIN ----------------

@app.route("/login",methods=["GET","POST"])
def login():

    if request.method=="POST":

        username=request.form["username"]
        password=request.form["password"]

        conn=sqlite3.connect("users.db")
        cursor=conn.cursor()

        cursor.execute(
        "SELECT password FROM users WHERE username=?",
        (username,)
        )

        user=cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[0],password):

            session["user"]=username
            return redirect(url_for("home"))

        else:
            return "Invalid login"

    return render_template("login.html")



# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.pop("user",None)
    return redirect(url_for("login"))



# ---------------- ANALYZE RESUME ----------------

@app.route("/analyze",methods=["POST"])
def analyze():

    if "user" not in session:
        return redirect(url_for("login"))

    file=request.files["resume"]

    filename=secure_filename(file.filename)

    filepath=os.path.join(app.config["UPLOAD_FOLDER"],filename)

    file.save(filepath)

    resume_text=extract_text_from_pdf(filepath)

    results={}
    suggestion_list=[]

    for job,skills in job_roles.items():

        matched=[s for s in skills if s in resume_text]

        percentage=int((len(matched)/len(skills))*100)

        missing=list(set(skills)-set(matched))

        for m in missing:
            if m in suggestions:
                suggestion_list.append(suggestions[m])

        results[job]={
        "percentage":percentage,
        "matched_skills":matched,
        "missing_skills":missing
        }

    best_match=max(results,key=lambda x:results[x]["percentage"])
    score=results[best_match]["percentage"]

    session["results"]=results
    session["best_match"]=best_match

    # save history
    conn=sqlite3.connect("users.db")
    cursor=conn.cursor()

    cursor.execute(
    "INSERT INTO history(username,best_match,score,date) VALUES (?,?,?,?)",
    (session["user"],best_match,score,str(datetime.datetime.now()))
    )

    conn.commit()
    conn.close()

    return render_template(
    "result.html",
    results=results,
    best_match=best_match,
    suggestions=suggestion_list,
    score=score
    )



# ---------------- HISTORY ----------------

@app.route("/history")
def history():

    if "user" not in session:
        return redirect(url_for("login"))

    conn=sqlite3.connect("users.db")
    cursor=conn.cursor()

    cursor.execute(
    "SELECT best_match,score,date FROM history WHERE username=?",
    (session["user"],)
    )

    data=cursor.fetchall()
    conn.close()

    return render_template("history.html",data=data)



# ---------------- DOWNLOAD PDF ----------------

@app.route("/download")
def download_pdf():

    if "results" not in session:
        return redirect(url_for("home"))

    results=session["results"]
    best_match=session["best_match"]
    username=session["user"]

    file_path="resume_report.pdf"

    styles=getSampleStyleSheet()
    elements=[]

    elements.append(Paragraph("Resume Analysis Report",styles["Title"]))
    elements.append(Spacer(1,20))

    elements.append(Paragraph(f"User : {username}",styles["Normal"]))
    elements.append(Paragraph(f"Best Job Match : {best_match}",styles["Normal"]))
    elements.append(Spacer(1,20))

    for job,data in results.items():

        elements.append(
        Paragraph(f"{job} - {data['percentage']}%",styles["Heading3"])
        )

        elements.append(
        Paragraph(f"Matched Skills : {', '.join(data['matched_skills'])}",styles["Normal"])
        )

        elements.append(
        Paragraph(f"Missing Skills : {', '.join(data['missing_skills'])}",styles["Normal"])
        )

        elements.append(Spacer(1,15))

    doc=SimpleDocTemplate(file_path)
    doc.build(elements)

    return send_file(file_path,as_attachment=True)



if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)