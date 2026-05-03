from flask import Flask, render_template, request, redirect, session
import sqlite3
import joblib
import pandas as pd
from groq import Groq
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ===== LOAD MODEL =====
model = joblib.load("models/churn_model.pkl")
scaler = joblib.load("models/scaler.pkl")
feature_names = joblib.load("models/feature_names.pkl")

# ===== GROQ =====
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ===== DB INIT =====
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        gender INTEGER,
        senior INTEGER,
        partner INTEGER,
        dependents INTEGER,
        tenure INTEGER,
        phone INTEGER,
        multiple INTEGER,
        security INTEGER,
        backup INTEGER,
        protection INTEGER,
        tech INTEGER,
        tv INTEGER,
        movies INTEGER,
        contract INTEGER,
        paperless INTEGER,
        payment INTEGER,
        monthly REAL,
        total REAL,
        cltv REAL,
        churn_probability REAL,
        risk_level TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ===== HOME =====
@app.route("/")
def home():
    return redirect("/login")

# ===== REGISTER =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("INSERT INTO users VALUES (NULL,?,?,?)",
                  (request.form["username"],
                   request.form["password"],
                   request.form["role"].lower()))

        conn.commit()
        conn.close()
        return redirect("/login")

    return render_template("register.html")

# ===== LOGIN =====
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?",
                  (request.form["username"],
                   request.form["password"]))

        user = c.fetchone()
        conn.close()

        if user:
            session["user"] = user[1]
            session["role"] = user[3]

            if user[3] == "admin":
                return redirect("/dashboard")
            else:
                return redirect("/submit_details")

    return render_template("login.html")

# ===== CUSTOMER SUBMIT =====
@app.route("/submit_details", methods=["GET","POST"])
def submit_details():
    if "user" not in session or session["role"] != "customer":
        return redirect("/login")

    if request.method == "POST":

        df = pd.DataFrame([{
            "Count":1,
            "Country":0,
            "State":0,
            "City":0,
            "Gender":int(request.form["Gender"]),
            "Senior Citizen":int(request.form["Senior Citizen"]),
            "Partner":int(request.form["Partner"]),
            "Dependents":int(request.form["Dependents"]),
            "Tenure Months":int(request.form["Tenure Months"]),
            "Phone Service":int(request.form["Phone Service"]),
            "Multiple Lines":int(request.form["Multiple Lines"]),
            "Internet Service":1,
            "Online Security":int(request.form["Online Security"]),
            "Online Backup":int(request.form["Online Backup"]),
            "Device Protection":int(request.form["Device Protection"]),
            "Tech Support":int(request.form["Tech Support"]),
            "Streaming TV":int(request.form["Streaming TV"]),
            "Streaming Movies":int(request.form["Streaming Movies"]),
            "Contract":int(request.form["Contract"]),
            "Paperless Billing":int(request.form["Paperless Billing"]),
            "Payment Method":int(request.form["Payment Method"]),
            "Monthly Charges":float(request.form["Monthly Charges"]),
            "Total Charges":float(request.form["Total Charges"]),
            "CLTV":float(request.form["CLTV"])
        }])

        df = df[feature_names]
        scaled = scaler.transform(df)

        probability = model.predict_proba(scaled)[0][1]

        # ===== RISK LOGIC =====
        if probability >= 0.5:
            risk = "HIGH"
        elif probability >= 0.3:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
        INSERT INTO customers VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            request.form["name"],
            int(request.form["Gender"]),
            int(request.form["Senior Citizen"]),
            int(request.form["Partner"]),
            int(request.form["Dependents"]),
            int(request.form["Tenure Months"]),
            int(request.form["Phone Service"]),
            int(request.form["Multiple Lines"]),
            int(request.form["Online Security"]),
            int(request.form["Online Backup"]),
            int(request.form["Device Protection"]),
            int(request.form["Tech Support"]),
            int(request.form["Streaming TV"]),
            int(request.form["Streaming Movies"]),
            int(request.form["Contract"]),
            int(request.form["Paperless Billing"]),
            int(request.form["Payment Method"]),
            float(request.form["Monthly Charges"]),
            float(request.form["Total Charges"]),
            float(request.form["CLTV"]),
            float(probability),
            risk
        ))

        conn.commit()
        conn.close()

        return redirect("/submit_details")

    return render_template("submit_details.html")

# ===== DASHBOARD =====
@app.route("/dashboard")
def dashboard():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM customers")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM customers WHERE risk_level='HIGH'")
    high = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM customers WHERE risk_level='MEDIUM'")
    medium = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM customers WHERE risk_level='LOW'")
    low = c.fetchone()[0]

    conn.close()

    return render_template("dashboard.html",
                           total=total,
                           high_risk=high,
                           medium_risk=medium,
                           low_risk=low)

# ===== CUSTOMERS =====
@app.route("/customers")
def customers():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM customers")
    data = c.fetchall()

    conn.close()

    return render_template("customers.html", data=data)

# ===== GROQ RETENTION =====
@app.route("/retention/<int:id>")
def retention(id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM customers WHERE id=?", (id,))
    customer = c.fetchone()
    conn.close()

    prompt = f"""
Customer churn probability: {customer['churn_probability']}
Risk level: {customer['risk_level']}

Give retention strategy strictly like:

1. ...
2. ...
3. ...
4. ...
5. ...

Rules:
- Each in new line
- No paragraph
- Short points
"""

    response = client.chat.completions.create(
        messages=[
            {"role":"system","content":"You are telecom retention expert"},
            {"role":"user","content":prompt}
        ],
        model="llama-3.1-8b-instant"
    )

    strategy = response.choices[0].message.content

    return render_template(
        "retention.html",
        customer=customer,
        strategy=strategy
    )

# ===== LOGOUT =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ===== RUN (FIXED FOR DEPLOYMENT) =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))