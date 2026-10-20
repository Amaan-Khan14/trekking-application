from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, event, text
from sqlalchemy.engine import Engine

db = SQLAlchemy()

ROLES = ("admin", "staff", "trekker")
USER_STATUSES = ("active", "inactive", "blacklisted")
DIFFICULTIES = ("Easy", "Moderate", "Hard")
TREK_STATUSES = ("Pending", "Approved", "Open", "Closed", "Completed")
BOOKING_STATUSES = ("Booked", "Cancelled", "Completed")
PAYMENT_STATUSES = ("Pending", "Paid", "Refunded")
EXPORT_STATUSES = ("Pending", "Done", "Failed")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


@event.listens_for(Engine, "connect")
def _enable_sqlite_fks(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


class User(db.Model):
    """Unified account table for admin, staff and trekkers."""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="trekker")
    status = db.Column(db.String(12), nullable=False, default="active")
    phone = db.Column(db.String(20))
    emergency_contact = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    staff_profile = db.relationship("StaffProfile", back_populates="user", uselist=False)
    bookings = db.relationship("Booking", back_populates="user")

    __table_args__ = (
        CheckConstraint(_in("role", ROLES), name="ck_user_role"),
        CheckConstraint(_in("status", USER_STATUSES), name="ck_user_status"),
        # Only one admin may ever exist.
        Index("uq_single_admin", "role", unique=True, sqlite_where=text("role = 'admin'")),
    )


class StaffProfile(db.Model):
    __tablename__ = "staff_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    contact_details = db.Column(db.String(200))
    specialization = db.Column(db.String(100))
    status = db.Column(db.String(12), nullable=False, default="active")

    user = db.relationship("User", back_populates="staff_profile")
    treks = db.relationship("Trek", back_populates="staff")

    __table_args__ = (CheckConstraint(_in("status", USER_STATUSES), name="ck_staff_status"),)


class Trek(db.Model):
    __tablename__ = "trek"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    difficulty = db.Column(db.String(10), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="Pending")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("staff_profile.id"))
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)  # included in reminder emails
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)  # soft delete keeps history
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    staff = db.relationship("StaffProfile", back_populates="treks")
    bookings = db.relationship("Booking", back_populates="trek")

    __table_args__ = (
        CheckConstraint(_in("difficulty", DIFFICULTIES), name="ck_trek_difficulty"),
        CheckConstraint(_in("status", TREK_STATUSES), name="ck_trek_status"),
        CheckConstraint("duration_days > 0", name="ck_trek_duration"),
        CheckConstraint("total_slots >= 0", name="ck_trek_total_slots"),
        CheckConstraint("available_slots >= 0 AND available_slots <= total_slots", name="ck_trek_available_slots"),
        CheckConstraint("end_date >= start_date", name="ck_trek_dates"),
        Index("ix_trek_search", "status", "difficulty", "location"),
        Index("ix_trek_staff", "assigned_staff_id"),
    )


class Booking(db.Model):
    """Link table between users and treks (many-to-many) with its own state."""

    __tablename__ = "booking"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("trek.id"), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(10), nullable=False, default="Booked")
    payment_status = db.Column(db.String(10), nullable=False, default="Pending")

    user = db.relationship("User", back_populates="bookings")
    trek = db.relationship("Trek", back_populates="bookings")

    __table_args__ = (
        CheckConstraint(_in("status", BOOKING_STATUSES), name="ck_booking_status"),
        CheckConstraint(_in("payment_status", PAYMENT_STATUSES), name="ck_booking_payment"),
        # One live booking per user per trek; a cancelled one can be rebooked.
        Index("uq_active_booking", "user_id", "trek_id", unique=True, sqlite_where=text("status = 'Booked'")),
        Index("ix_booking_user", "user_id"),
        Index("ix_booking_trek", "trek_id"),
    )


class ExportJob(db.Model):
    """Tracks a user-triggered CSV export of booking history."""

    __tablename__ = "export_job"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="Pending")
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (CheckConstraint(_in("status", EXPORT_STATUSES), name="ck_export_status"),)


class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_notification_user", "user_id", "is_read"),)
