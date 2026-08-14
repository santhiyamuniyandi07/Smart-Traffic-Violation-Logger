from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import qrcode
import os
import urllib.parse
import sqlite3


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# DATABASE MODEL
# =========================================================

class Violation(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    vehicle_number = db.Column(
        db.String(20),
        nullable=False
    )

    violation_type = db.Column(
        db.String(100),
        nullable=False
    )

    location = db.Column(
        db.String(200),
        nullable=False
    )

    date = db.Column(
        db.String(20),
        nullable=False
    )

    fine_amount = db.Column(
        db.Float,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="Unpaid"
    )

    payment_method = db.Column(
        db.String(30),
        default="Unpaid"
    )

    payment_time = db.Column(
        db.DateTime,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# DATABASE MIGRATION
# =========================================================

def update_database():

    db_path = os.path.join(
        app.instance_path,
        "database.db"
    )

    os.makedirs(
        app.instance_path,
        exist_ok=True
    )

    if not os.path.exists(db_path):
        return

    connection = sqlite3.connect(db_path)

    cursor = connection.cursor()

    cursor.execute(
        "PRAGMA table_info(violation)"
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    # -----------------------------------------------------
    # Add payment_method if missing
    # -----------------------------------------------------

    if "payment_method" not in columns:

        cursor.execute(
            """
            ALTER TABLE violation
            ADD COLUMN payment_method
            VARCHAR(30)
            DEFAULT 'Unpaid'
            """
        )

    # -----------------------------------------------------
    # Add payment_time if missing
    # -----------------------------------------------------

    if "payment_time" not in columns:

        cursor.execute(
            """
            ALTER TABLE violation
            ADD COLUMN payment_time
            DATETIME
            """
        )

    connection.commit()

    connection.close()


# =========================================================
# HOME / DASHBOARD
# =========================================================

@app.route("/")
def index():

    violations = Violation.query.order_by(
        Violation.id.desc()
    ).all()

    total_violations = len(violations)

    paid_violations = Violation.query.filter_by(
        status="Paid"
    ).count()

    unpaid_violations = Violation.query.filter_by(
        status="Unpaid"
    ).count()

    total_fine = sum(
        v.fine_amount
        for v in violations
    )

    paid_amount = sum(
        v.fine_amount
        for v in violations
        if v.status == "Paid"
    )

    unpaid_amount = sum(
        v.fine_amount
        for v in violations
        if v.status == "Unpaid"
    )

    return render_template(
        "index.html",
        violations=violations[:10],
        total_violations=total_violations,
        paid_violations=paid_violations,
        unpaid_violations=unpaid_violations,
        total_fine=total_fine,
        paid_amount=paid_amount,
        unpaid_amount=unpaid_amount
    )


# =========================================================
# ADD VIOLATION
# =========================================================

@app.route(
    "/add",
    methods=["GET", "POST"]
)
def add_violation():

    if request.method == "POST":

        # -------------------------------------------------
        # GET FORM VALUES
        # -------------------------------------------------

        vehicle_number = request.form[
            "vehicle_number"
        ].strip().upper()

        violation_type = request.form[
            "violation_type"
        ]

        location = request.form[
            "location"
        ].strip()

        date = request.form[
            "date"
        ]

        fine_amount = float(
            request.form[
                "fine_amount"
            ]
        )

        payment_method = request.form.get(
            "payment_method",
            "Unpaid"
        )


        # -------------------------------------------------
        # PAYMENT STATUS
        # -------------------------------------------------

        if payment_method == "Paid On Spot":

            status = "Paid"

            payment_time = datetime.now()

        elif payment_method == "UPI":

            status = "Unpaid"

            payment_time = None

        else:

            payment_method = "Unpaid"

            status = "Unpaid"

            payment_time = None


        # -------------------------------------------------
        # CREATE VIOLATION
        # -------------------------------------------------

        violation = Violation(

            vehicle_number=vehicle_number,

            violation_type=violation_type,

            location=location,

            date=date,

            fine_amount=fine_amount,

            status=status,

            payment_method=payment_method,

            payment_time=payment_time
        )


        # -------------------------------------------------
        # SAVE DATABASE
        # -------------------------------------------------

        db.session.add(violation)

        db.session.commit()


        # =================================================
        # QR CODE FOLDER
        # =================================================

        qr_folder = os.path.join(
            app.static_folder,
            "qr_codes"
        )

        os.makedirs(
            qr_folder,
            exist_ok=True
        )


        # =================================================
        # VIOLATION STATUS URL
        # =================================================

        status_url = url_for(
            "public_status",
            violation_id=violation.id,
            _external=True
        )


        # =================================================
        # VIOLATION STATUS QR
        # =================================================

        violation_qr = qrcode.make(
            status_url
        )

        violation_qr_filename = (
            f"violation_{violation.id}.png"
        )

        violation_qr_path = os.path.join(
            qr_folder,
            violation_qr_filename
        )

        violation_qr.save(
            violation_qr_path
        )

        violation_qr_url = url_for(
            "static",
            filename=(
                f"qr_codes/"
                f"{violation_qr_filename}"
            )
        )


        # =================================================
        # UPI PAYMENT QR
        # =================================================

        payment_qr_url = None

        if payment_method == "UPI":

            # IMPORTANT:
            # Change this to your REAL UPI ID.

            upi_id = "santhiyamuniyandi@oksbi"

            payee_name = (
                "Smart Traffic Logger"
            )

            transaction_note = (
                f"Traffic Fine - "
                f"{vehicle_number}"
            )


            # -------------------------------------------------
            # CREATE UPI LINK
            # -------------------------------------------------

            upi_link = (
                "upi://pay?"
                + urllib.parse.urlencode({

                    "pa": upi_id,

                    "pn": payee_name,

                    "am": (
                        f"{fine_amount:.2f}"
                    ),

                    "cu": "INR",

                    "tn": transaction_note

                })
            )


            # -------------------------------------------------
            # CREATE PAYMENT QR
            # -------------------------------------------------

            payment_qr = qrcode.make(
                upi_link
            )

            payment_qr_filename = (
                f"payment_{violation.id}.png"
            )

            payment_qr_path = os.path.join(
                qr_folder,
                payment_qr_filename
            )

            payment_qr.save(
                payment_qr_path
            )

            payment_qr_url = url_for(
                "static",
                filename=(
                    f"qr_codes/"
                    f"{payment_qr_filename}"
                )
            )


        # =================================================
        # SHOW RESULT
        # =================================================

        return render_template(

            "add_violation.html",

            violation=violation,

            saved=True,

            status_url=status_url,

            qr_url=violation_qr_url,

            violation_qr_url=violation_qr_url,

            payment_qr_url=payment_qr_url
        )


    # =================================================
    # GET REQUEST
    # =================================================

    return render_template(
        "add_violation.html",
        saved=False
    )


# =========================================================
# MARK VIOLATION AS PAID
# =========================================================

@app.route(
    "/pay/<int:id>",
    methods=["POST"]
)
def mark_paid(id):

    violation = Violation.query.get_or_404(
        id
    )

    violation.status = "Paid"

    violation.payment_time = datetime.now()


    # If payment method was Unpaid,
    # change it to UPI after payment.

    if violation.payment_method in [
        "Unpaid",
        None,
        ""
    ]:

        violation.payment_method = "UPI"


    db.session.commit()


    return redirect(
        request.referrer
        or url_for("index")
    )


# =========================================================
# DELETE VIOLATION
# =========================================================

@app.route(
    "/delete/<int:id>",
    methods=["POST"]
)
def delete_violation(id):

    # -----------------------------------------------------
    # FIND VIOLATION
    # -----------------------------------------------------

    violation = Violation.query.get_or_404(
        id
    )


    # -----------------------------------------------------
    # QR CODE FOLDER
    # -----------------------------------------------------

    qr_folder = os.path.join(
        app.static_folder,
        "qr_codes"
    )


    # -----------------------------------------------------
    # VIOLATION STATUS QR
    # -----------------------------------------------------

    violation_qr = os.path.join(
        qr_folder,
        f"violation_{violation.id}.png"
    )


    # -----------------------------------------------------
    # PAYMENT QR
    # -----------------------------------------------------

    payment_qr = os.path.join(
        qr_folder,
        f"payment_{violation.id}.png"
    )


    # -----------------------------------------------------
    # DELETE VIOLATION QR
    # -----------------------------------------------------

    if os.path.exists(
        violation_qr
    ):

        os.remove(
            violation_qr
        )


    # -----------------------------------------------------
    # DELETE PAYMENT QR
    # -----------------------------------------------------

    if os.path.exists(
        payment_qr
    ):

        os.remove(
            payment_qr
        )


    # -----------------------------------------------------
    # DELETE DATABASE RECORD
    # -----------------------------------------------------

    db.session.delete(
        violation
    )

    db.session.commit()


    # -----------------------------------------------------
    # RETURN TO PREVIOUS PAGE
    # -----------------------------------------------------

    return redirect(
        request.referrer
        or url_for("history")
    )


# =========================================================
# HISTORY
# =========================================================

@app.route("/history")
def history():

    vehicle = request.args.get(
        "vehicle",
        ""
    )

    status = request.args.get(
        "status",
        ""
    )

    violation_type = request.args.get(
        "type",
        ""
    )


    # -----------------------------------------------------
    # START QUERY
    # -----------------------------------------------------

    query = Violation.query


    # -----------------------------------------------------
    # VEHICLE FILTER
    # -----------------------------------------------------

    if vehicle:

        query = query.filter(
            Violation.vehicle_number.ilike(
                f"%{vehicle}%"
            )
        )


    # -----------------------------------------------------
    # STATUS FILTER
    # -----------------------------------------------------

    if status:

        query = query.filter(
            Violation.status == status
        )


    # -----------------------------------------------------
    # VIOLATION TYPE FILTER
    # -----------------------------------------------------

    if violation_type:

        query = query.filter(
            Violation.violation_type
            == violation_type
        )


    # -----------------------------------------------------
    # GET RESULTS
    # -----------------------------------------------------

    violations = query.order_by(
        Violation.id.desc()
    ).all()


    return render_template(
        "history.html",
        violations=violations
    )


# =========================================================
# PUBLIC STATUS PAGE
# =========================================================

@app.route(
    "/status/<int:violation_id>"
)
def public_status(violation_id):

    violation = Violation.query.get_or_404(
        violation_id
    )

    return render_template(
        "public_status.html",
        violation=violation
    )


# =========================================================
# CREATE DATABASE
# =========================================================

with app.app_context():

    db.create_all()

    update_database()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
