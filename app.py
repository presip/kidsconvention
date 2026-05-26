from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from collections import defaultdict
from sqlalchemy import func
from datetime import datetime

from models import db, User, Kid, Attendance, Event, EventParticipant

app = Flask(__name__)

app.secret_key = "kids-convention-secret"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///kids_convention.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# ---------------------------------------------------
# CREATE DATABASE + DEFAULT ADMIN
# ---------------------------------------------------

with app.app_context():

    db.create_all()

    admin_exists = User.query.filter_by(username="admin").first()

    if not admin_exists:

        admin = User(
            username="admin",
            password=generate_password_hash("admin123")
        )

        db.session.add(admin)
        db.session.commit()

# ---------------------------------------------------
# LOGIN MANAGER
# ---------------------------------------------------

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# ---------------------------------------------------
# FLASK LOGIN SESSION USER
# ---------------------------------------------------

class LoginUser(UserMixin):

    def __init__(self, username):
        self.id = username

# ---------------------------------------------------
# USER LOADER
# ---------------------------------------------------

@login_manager.user_loader
def load_user(username):

    user = User.query.filter_by(username=username).first()

    if user:
        return LoginUser(user.username)

    return None

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def is_admin():
    return current_user.id == "admin"

def age_group(age):

    age = int(age)
    if age <= 3:
        return "B"
    elif age <= 5:
        return "K"
    elif age <= 8:
        return "P"
    elif age <= 10:
        return "M"
    elif age <= 12:
        return "J"
    elif age <= 15:
        return "T"
    else:
        return "A"

def next_kid_id(age_group):

    kids = Kid.query.filter(
        Kid.kid_id.like(f"{age_group}%")
    ).all()

    if not kids:
        return f"{age_group}001"

    nums = []

    for k in kids:
        nums.append(int(k.kid_id[1:]))

    return f"{age_group}{max(nums)+1:03d}"

# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------

@app.route("/")
@login_required
def dashboard():

    today = datetime.now().strftime("%Y-%m-%d")

    # ---------------------------------------------------
    # TOTAL REGISTRATIONS TODAY
    # ---------------------------------------------------

    total_registrations_today = Kid.query.filter(
        Kid.registered_at.like(f"{today}%")
    ).count()

    # ---------------------------------------------------
    # TOTAL REGISTRATIONS CUMULATIVE
    # ---------------------------------------------------

    total_registrations_total = Kid.query.count()

    # ---------------------------------------------------
    # TOTAL VISITORS TODAY
    # Visitor = parent_kid_id NOT blank
    # ---------------------------------------------------

    total_visitors_today = Kid.query.filter(
        Kid.registered_at.like(f"{today}%"),
        Kid.parent_kid_id != "",
        Kid.parent_kid_id.isnot(None)
    ).count()

    # ---------------------------------------------------
    # TOTAL VISITORS CUMULATIVE
    # ---------------------------------------------------

    total_visitors_total = Kid.query.filter(
        Kid.parent_kid_id != "",
        Kid.parent_kid_id.isnot(None)
    ).count()

    # ---------------------------------------------------
    # ATTENDANCE COUNTS
    # ---------------------------------------------------

    total_attendance_today = Attendance.query.filter(
        Attendance.day == today
    ).count()

    total_attendance_total = Attendance.query.count()

    return render_template(
        "dashboard.html",

        total_registrations_today=total_registrations_today,
        total_registrations_total=total_registrations_total,

        total_visitors_today=total_visitors_today,
        total_visitors_total=total_visitors_total,

        total_attendance_today=total_attendance_today,
        total_attendance_total=total_attendance_total
    )

# ---------------------------------------------------
# LOGIN
# ---------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):

            login_user(LoginUser(user.username))

            return redirect(url_for("dashboard"))

        flash("Invalid Login", "danger")

    return render_template("login.html")

# ---------------------------------------------------
# LOGOUT
# ---------------------------------------------------

@app.route("/logout")
def logout():

    logout_user()

    return redirect(url_for("login"))

# ---------------------------------------------------
# USER MANAGEMENT
# ---------------------------------------------------

@app.route("/users", methods=["GET", "POST"])
@login_required
def users():

    if not is_admin():

        flash("Only admin can manage users", "danger")

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        phonenumber = request.form["phonenumber"]
        fullname = request.form["fullname"]

        existing = User.query.filter_by(username=username).first()

        if existing:

            flash("User already exists","danger")

            return redirect(url_for("users"))

        new_user = User(
            username=username,
            password=generate_password_hash(password),
            phonenumber = phonenumber,
            fullname = fullname
        )

        db.session.add(new_user)
        db.session.commit()

        flash("User Created","success")

    users = User.query.all()

    return render_template("users.html", users=users)

# ---------------------------------------------------
# REGISTER KID
# ---------------------------------------------------

@app.route("/register_kid", methods=["GET", "POST"])
@login_required
def register_kid():
    kids = Kid.query.all()
    if request.method == "POST":

        name = request.form["name"]
        age = request.form["age"]
        locality = request.form["locality"]
        contactnumber = request.form["contactnumber"]
        city = request.form["city"]
        parent_kid_id = request.form["parent_kid_id"].strip()

        # ---------------------------------------------------
        # VALIDATE PARENT KID ID
        # ---------------------------------------------------

        if parent_kid_id != "":
            parent_exists = Kid.query.filter_by(
                kid_id=parent_kid_id
            ).first()
            if not parent_exists:
                flash(
                    "Invalid Referrer Kid ID",
                    "danger"
                )
                return redirect(url_for("register_kid"))

        grp = age_group(age)

        kid_id = next_kid_id(grp)

        new_kid = Kid(
            kid_id=kid_id,
            name=name,
            age=age,
            age_group=grp,
            locality=locality,
            contactnumber=contactnumber,
            city=city,
            parent_kid_id=parent_kid_id,
            registered_by=current_user.id,
            registered_at=datetime.now().isoformat()
        )

        db.session.add(new_kid)
        db.session.commit()

        # ---------------------------------------------------
        # AUTO MARK ATTENDANCE
        # ---------------------------------------------------

        today = datetime.now().strftime("%Y-%m-%d")

        existing_attendance = Attendance.query.filter_by(
            kid_id=kid_id,
            day=today
        ).first()

        if not existing_attendance:

            attendance = Attendance(
                kid_id=kid_id,
                day=today,
                marked_by=current_user.id,
                marked_at=datetime.now().isoformat()
            )

            db.session.add(attendance)
            db.session.commit()

            flash(
                f"Kid Registered and Attendance Marked: {kid_id}",
                "success"
            )
    return render_template("register_kid.html",kids=kids)

# ---------------------------------------------------
# VIEW KIDS
# ---------------------------------------------------

@app.route("/kids")
@login_required
def kids():

    kids = Kid.query.all()

    return render_template("kids.html", kids=kids)

# ---------------------------------------------------
# ATTENDANCE
# ---------------------------------------------------

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():

    kids = Kid.query.all()

    selected_kid = None
    attendance_history = []

    today = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":

        kid_id = request.form["kid_id"]
        action = request.form["action"]

        # ---------------------------------------------------
        # VALIDATE KID
        # ---------------------------------------------------

        selected_kid = Kid.query.filter_by(
            kid_id=kid_id
        ).first()

        if not selected_kid:

            flash("Invalid Kid ID", "danger")

            return redirect(url_for("attendance"))

        # ---------------------------------------------------
        # FETCH HISTORY
        # ---------------------------------------------------

        attendance_history = Attendance.query.filter_by(
            kid_id=kid_id
        ).order_by(
            Attendance.marked_at.desc()
        ).all()

        # ---------------------------------------------------
        # ONLY FETCH HISTORY
        # ---------------------------------------------------

        if action == "history":

            return render_template(
                "attendance.html",
                kids=kids,
                selected_kid=selected_kid,
                attendance_history=attendance_history,
                today=today
            )

        # ---------------------------------------------------
        # CHECK TODAY DUPLICATE
        # ---------------------------------------------------

        existing = Attendance.query.filter(
            Attendance.kid_id == kid_id,
            Attendance.day == today
        ).first()

        if existing:

            flash(
                "Attendance already marked for today",
                "warning"
            )

            return render_template(
                "attendance.html",
                kids=kids,
                selected_kid=selected_kid,
                attendance_history=attendance_history,
                today=today
            )

        # ---------------------------------------------------
        # SAVE ATTENDANCE
        # ---------------------------------------------------

        entry = Attendance(
            kid_id=kid_id,
            day=today,
            marked_by=current_user.id,
            marked_at=datetime.now().isoformat()
        )

        db.session.add(entry)
        db.session.commit()

        flash("Attendance Marked", "success")

        # Refresh history
        attendance_history = Attendance.query.filter_by(
            kid_id=kid_id
        ).order_by(
            Attendance.marked_at.desc()
        ).all()

    return render_template(
        "attendance.html",
        kids=kids,
        selected_kid=selected_kid,
        attendance_history=attendance_history,
        today=today
    )

#----------------------------------------------------
# EDIT KID
#----------------------------------------------------
@app.route("/edit_kid/<kid_id>", methods=["GET", "POST"])
@login_required
def edit_kid(kid_id):

    kid = Kid.query.filter_by(
        kid_id=kid_id
    ).first()

    if not kid:

        flash("Kid not found", "danger")

        return redirect(url_for("kids"))

    kids = Kid.query.all()

    if request.method == "POST":

        # ---------------------------------------------------
        # VALIDATE REFERRAL
        # ---------------------------------------------------

        parent_kid_id = request.form["parent_kid_id"].strip()

        if parent_kid_id != "":

            parent_exists = Kid.query.filter_by(
                kid_id=parent_kid_id
            ).first()

            if not parent_exists:

                flash(
                    "Invalid Referral Kid ID",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_kid",
                        kid_id=kid_id
                    )
                )

        # ---------------------------------------------------
        # UPDATE FIELDS
        # ---------------------------------------------------

        kid.name = request.form["name"]
        kid.locality = request.form["locality"]
        kid.city = request.form["city"]
        kid.contactnumber = request.form["contactnumber"]
        kid.parent_kid_id = parent_kid_id

        db.session.commit()

        flash("Kid Details Updated", "success")

        return redirect(url_for("kids"))

    return render_template(
        "edit_kid.html",
        kid=kid,
        kids=kids
    )
    
#----------------------------------------------------
#  KID PROFILE VIEW
#----------------------------------------------------

@app.route("/kid/<kid_id>")
@login_required
def kid_details(kid_id):

    # ---------------------------------------------------
    # FETCH KID
    # ---------------------------------------------------

    kid = Kid.query.filter_by(
        kid_id=kid_id
    ).first()

    if not kid:

        flash("Kid not found", "danger")

        return redirect(url_for("kids"))

    # ---------------------------------------------------
    # FETCH REFERRALS
    # ---------------------------------------------------

    referrals = Kid.query.filter_by(
        parent_kid_id=kid_id
    ).all()

    # ---------------------------------------------------
    # FETCH ATTENDANCE
    # ---------------------------------------------------

    attendance = Attendance.query.filter_by(
        kid_id=kid_id
    ).order_by(
        Attendance.marked_at
    ).all()

    # ---------------------------------------------------
    # FETCH EVENT PARTICIPATION
    # ---------------------------------------------------

    event_participation = db.session.query(
        EventParticipant,
        Event
    ).join(
        Event,
        EventParticipant.event_id == Event.event_id
    ).filter(
        EventParticipant.kid_id == kid_id
    ).all()

    return render_template(

        "kid_details.html",

        kid=kid,
        referrals=referrals,
        attendance=attendance,
        event_participation=event_participation

    )

# ---------------------------------------------------
# EVENTs
# ---------------------------------------------------

@app.route("/events", methods=["GET", "POST"])
@login_required
def events():

    events = Event.query.order_by(
        Event.created_at.desc()
    ).all()

    event_data = []

    for e in events:

        participants = db.session.query(
            EventParticipant,
            Kid
        ).join(
            Kid,
            EventParticipant.kid_id == Kid.kid_id
        ).filter(
            EventParticipant.event_id == e.event_id
        ).all()

        participant_list = []

        for ep, kid in participants:

            participant_list.append({
                "kid_id": kid.kid_id,
                "name": kid.name,
                "age": kid.age,
                "city": kid.city
            })

        event_data.append({
            "event": e,
            "participants": participant_list
        })

    return render_template(
        "events.html",
        event_data=event_data
    )
    
# ---------------------------------------------------
# CREATE EVENT
# ---------------------------------------------------

@app.route("/create_event", methods=["GET", "POST"])
@login_required
def create_event():

    if request.method == "POST":

        event_name = request.form["event_name"]

        event_id = "E" + str(int(datetime.now().timestamp()))

        event = Event(
            event_id=event_id,
            event_name=event_name,
            created_by=current_user.id,
            created_at=datetime.now().isoformat()
        )

        db.session.add(event)
        db.session.commit()

        flash("Event Created")

    events = Event.query.all()
    return render_template("create_event.html", events = events)

# ---------------------------------------------------
# EVENT PARTICIPANTS
# ---------------------------------------------------

@app.route("/event_participants", methods=["GET", "POST"])
@login_required
def event_participants():

    events = Event.query.all()

    kids = Kid.query.all()

    if request.method == "POST":

        kid_id = request.form["kid_id"]

        kid_exists = Kid.query.filter_by(kid_id=kid_id).first()

        if not kid_exists:
            flash("Invalid Kid ID","danger")
            return redirect(url_for("event_participants"))
        
        event_id = request.form["event_id"]

        existing = EventParticipant.query.filter_by(
            kid_id=kid_id
        ).first()

        if existing:

            flash("Kid already participated","warning")

            return redirect(url_for("event_participants"))

        participant = EventParticipant(
            event_id=event_id,
            kid_id=kid_id,
            added_by=current_user.id,
            added_at=datetime.now().isoformat()
        )

        db.session.add(participant)
        db.session.commit()

        flash("Participant Added","success")

    participants = EventParticipant.query.all()

    return render_template(
        "event_participants.html",
        events=events,
        participants=participants,
        kids=kids
    )

# ---------------------------------------------------
# REPORTS
# ---------------------------------------------------

@app.route("/reports")
@login_required
def reports():

    return render_template(
        "reports.html"
    )

#----------------------------------------------------
#  Top Refferals
#----------------------------------------------------
@app.route("/reports/top_referrals")
@login_required
def top_referrals():

    results = db.session.query(
        Kid.parent_kid_id,
        db.func.count(Kid.id).label("total")
    ).filter(
        Kid.parent_kid_id != "",
        Kid.parent_kid_id.isnot(None)
    ).group_by(
        Kid.parent_kid_id
    ).order_by(
        db.desc("total")
    ).all()

    referral_data = []

    for parent_id, total in results:

        parent = Kid.query.filter_by(
            kid_id=parent_id
        ).first()

        if parent:

            referral_data.append({
                "kid_id": parent.kid_id,
                "name": parent.name,
                "total": total
            })

    return render_template(
        "top_referrals.html",
        referral_data=referral_data
    )

#----------------------------------------------------
#  Top Refferal Day
#----------------------------------------------------
@app.route("/reports/top_referrals_by_date", methods=["GET", "POST"])
@login_required
def top_referrals_by_date():

    referral_data = []
    selected_date = None

    if request.method == "POST":

        selected_date = request.form["selected_date"]

        results = db.session.query(
            Kid.parent_kid_id,
            db.func.count(Kid.id).label("total")
        ).filter(
            Kid.registered_at.like(f"{selected_date}%"),
            Kid.parent_kid_id != "",
            Kid.parent_kid_id.isnot(None)
        ).group_by(
            Kid.parent_kid_id
        ).order_by(
            db.desc("total")
        ).all()

        for parent_id, total in results:

            parent = Kid.query.filter_by(
                kid_id=parent_id
            ).first()

            if parent:

                referral_data.append({
                    "kid_id": parent.kid_id,
                    "name": parent.name,
                    "total": total
                })

    return render_template(
        "top_referrals_by_date.html",
        referral_data=referral_data,
        selected_date=selected_date
    )

#----------------------------------------------------
# Kids by Age Group
#----------------------------------------------------
@app.route("/reports/age_groups")
@login_required
def age_groups():

    groups = {}

    for grp in ["B", "K", "P", "M", "J", "T", "A" ]:

        groups[grp] = Kid.query.filter_by(
            age_group=grp
        ).all()

    return render_template(
        "age_groups.html",
        groups=groups
    )

#----------------------------------------------------
#  Attendance Reports
#----------------------------------------------------
@app.route("/reports/attendance")
@login_required
def attendance_report():

    kids = Kid.query.order_by(
        Kid.name
    ).all()

    # ---------------------------------------------------
    # FETCH UNIQUE DATES
    # ---------------------------------------------------

    attendance_dates = db.session.query(
        Attendance.day
    ).distinct().order_by(
        Attendance.day
    ).all()

    attendance_dates = [
        d[0]
        for d in attendance_dates
    ]

    attendance_data = []

    for kid in kids:

        attendance_entries = Attendance.query.filter_by(
            kid_id=kid.kid_id
        ).all()

        attended_days = set()

        for a in attendance_entries:
            attended_days.add(a.day)

        attendance_map = {}

        for d in attendance_dates:

            attendance_map[d] = (
                d in attended_days
            )

        attendance_data.append({

            "kid": kid,
            "attendance_map": attendance_map,
            "total_attendance": len(attended_days)

        })

    return render_template(

        "attendance_report.html",

        attendance_data=attendance_data,
        attendance_dates=attendance_dates

    )
    
#----------------------------------------------------
# AGE GROUP SUMMARY REPORTS
#----------------------------------------------------

@app.route("/reports/age_group_daily_summary")
@login_required
def age_group_daily_summary():

    # ---------------------------------------------------
    # FETCH ALL DATES
    # ---------------------------------------------------

    registration_dates = db.session.query(
        db.func.substr(Kid.registered_at, 1, 10)
    ).distinct().order_by(
        db.func.substr(Kid.registered_at, 1, 10)
    ).all()

    registration_dates = [
        d[0]
        for d in registration_dates
    ]

    attendance_dates = db.session.query(
        db.func.substr(Attendance.day, 1, 10)
    ).distinct().order_by(
        db.func.substr(Attendance.day, 1, 10)
    ).all()

    attendance_dates = [
        d[0]
        for d in attendance_dates
    ]

    all_dates = sorted(
        list(
            set(
                registration_dates + attendance_dates
            )
        )
    )

    # ---------------------------------------------------
    # AGE GROUPS
    # ---------------------------------------------------

    age_groups = [

        ("B", "Beginners"),
        ("K", "Kindergarten"),
        ("P", "Primary"),
        ("M", "Middlers"),
        ("J", "Juniors"),
        ("T", "Teens"),
        ("A", "Adults")

    ]

    summary = []

    for code, name in age_groups:

        row = {

            "code": code,
            "name": name,

            "registration": {},
            "attendance": {},
            "visitors": {},

            "total_registration": 0,
            "total_attendance": 0,
            "total_visitors": 0

        }

        # -----------------------------------------------
        # TOTALS
        # -----------------------------------------------

        row["total_registration"] = Kid.query.filter_by(
            age_group=code
        ).count()

        row["total_attendance"] = db.session.query(
            Attendance
        ).join(
            Kid,
            Attendance.kid_id == Kid.kid_id
        ).filter(
            Kid.age_group == code
        ).count()

        row["total_visitors"] = Kid.query.filter(
            Kid.age_group == code,
            Kid.parent_kid_id.isnot(None),
            Kid.parent_kid_id != ""
        ).count()

        # -----------------------------------------------
        # DATE WISE COUNTS
        # -----------------------------------------------

        for d in all_dates:

            # REGISTRATION

            reg_count = Kid.query.filter(
                Kid.age_group == code,
                Kid.registered_at.like(f"{d}%")
            ).count()

            row["registration"][d] = reg_count

            # ATTENDANCE

            att_count = db.session.query(
                Attendance
            ).join(
                Kid,
                Attendance.kid_id == Kid.kid_id
            ).filter(
                Kid.age_group == code,
                Attendance.day.like(f"{d}%")
            ).count()

            row["attendance"][d] = att_count

            # VISITORS

            vis_count = Kid.query.filter(
                Kid.age_group == code,
                Kid.parent_kid_id.isnot(None),
                Kid.parent_kid_id != "",
                Kid.registered_at.like(f"{d}%")
            ).count()

            row["visitors"][d] = vis_count

        summary.append(row)

    return render_template(

        "age_group_daily_summary.html",

        summary=summary,
        all_dates=all_dates

    )
    
#----------------------------------------------------
# ADMIN ONLY - VOLUNTEER PERFORMANCE
#----------------------------------------------------
@app.route("/reports/user_activity")
@login_required
def user_activity_report():

    # ---------------------------------------------------
    # ADMIN ONLY
    # ---------------------------------------------------

    if current_user.id != "admin":

        flash(
            "Access denied",
            "danger"
        )

        return redirect(url_for("dashboard"))

    # ---------------------------------------------------
    # FETCH ALL USERS
    # ---------------------------------------------------

    users = User.query.order_by(
        User.username
    ).all()

    # ---------------------------------------------------
    # FETCH ALL DATES
    # ---------------------------------------------------

    registration_dates = db.session.query(
        db.func.substr(Kid.registered_at, 1, 10)
    ).distinct().all()

    attendance_dates = db.session.query(
        db.func.substr(Attendance.marked_at, 1, 10)
    ).distinct().all()

    event_dates = db.session.query(
        db.func.substr(Event.created_at, 1, 10)
    ).distinct().all()

    participant_dates = db.session.query(
        db.func.substr(EventParticipant.added_at, 1, 10)
    ).distinct().all()

    all_dates = set()

    for d in registration_dates:
        all_dates.add(d[0])

    for d in attendance_dates:
        all_dates.add(d[0])

    for d in event_dates:
        all_dates.add(d[0])

    for d in participant_dates:
        all_dates.add(d[0])

    all_dates = sorted(list(all_dates))

    # ---------------------------------------------------
    # BUILD REPORT
    # ---------------------------------------------------

    report_data = []

    for user in users:

        row = {

            "username": user.username,

            "registrations": {},
            "attendance": {},
            "events": {},
            "participants": {},

            "total_registrations": 0,
            "total_attendance": 0,
            "total_events": 0,
            "total_participants": 0

        }

        # -----------------------------------------------
        # TOTALS
        # -----------------------------------------------

        row["total_registrations"] = Kid.query.filter_by(
            registered_by=user.username
        ).count()

        row["total_attendance"] = Attendance.query.filter_by(
            marked_by=user.username
        ).count()

        row["total_events"] = Event.query.filter_by(
            created_by=user.username
        ).count()

        row["total_participants"] = EventParticipant.query.filter_by(
            added_by=user.username
        ).count()

        # -----------------------------------------------
        # DAY-WISE COUNTS
        # -----------------------------------------------

        for d in all_dates:

            # REGISTRATIONS

            reg_count = Kid.query.filter(
                Kid.registered_by == user.username,
                Kid.registered_at.like(f"{d}%")
            ).count()

            row["registrations"][d] = reg_count

            # ATTENDANCE

            att_count = Attendance.query.filter(
                Attendance.marked_by == user.username,
                Attendance.marked_at.like(f"{d}%")
            ).count()

            row["attendance"][d] = att_count

            # EVENTS

            event_count = Event.query.filter(
                Event.created_by == user.username,
                Event.created_at.like(f"{d}%")
            ).count()

            row["events"][d] = event_count

            # PARTICIPANTS

            part_count = EventParticipant.query.filter(
                EventParticipant.added_by == user.username,
                EventParticipant.added_at.like(f"{d}%")
            ).count()

            row["participants"][d] = part_count

        report_data.append(row)

    return render_template(

        "user_activity_report.html",

        report_data=report_data,
        all_dates=all_dates

    )

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

if __name__ == "__main__":
    pass
    #app.run(host="0.0.0.0", port=5000)
