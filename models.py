from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    fullname = db.Column(db.String(200))
    phonenumber = db.Column(db.String(10))
    password = db.Column(db.String(500))

class Kid(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    kid_id = db.Column(db.String(20), unique=True)

    name = db.Column(db.String(200))
    age = db.Column(db.Integer)
    age_group = db.Column(db.String(5))

    locality = db.Column(db.String(200))
    city = db.Column(db.String(200))

    contactnumber = db.Column(db.String(10))

    parent_kid_id = db.Column(db.String(20))

    registered_by = db.Column(db.String(100))
    registered_at = db.Column(db.String(100))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    kid_id = db.Column(db.String(20))
    day = db.Column(db.String(20))

    marked_by = db.Column(db.String(100))
    marked_at = db.Column(db.String(100))

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    event_id = db.Column(db.String(50), unique=True)
    event_name = db.Column(db.String(200))

    created_by = db.Column(db.String(100))
    created_at = db.Column(db.String(100))

class EventParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    event_id = db.Column(db.String(50))
    kid_id = db.Column(db.String(20), unique=True)

    added_by = db.Column(db.String(100))
    added_at = db.Column(db.String(100))
