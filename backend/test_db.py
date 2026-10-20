from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from models import Booking, StaffProfile, Trek, User, db


@pytest.fixture
def app():
    app = create_app("sqlite:///:memory:")
    with app.app_context():
        yield app


def make_trek(**kw):
    t = Trek(name="T", location="L", difficulty="Easy", duration_days=2, total_slots=2,
             available_slots=2, status="Open", start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), **kw)
    db.session.add(t)
    db.session.commit()
    return t


def make_user(email="u@x.com", role="trekker"):
    u = User(name="U", email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    return u


def test_admin_seeded_once(app):
    assert User.query.filter_by(role="admin").count() == 1


def test_second_admin_rejected(app):
    with pytest.raises(IntegrityError):
        make_user("a2@x.com", role="admin")


def test_duplicate_active_booking_rejected_but_rebook_after_cancel(app):
    u, t = make_user(), make_trek()
    b = Booking(user_id=u.id, trek_id=t.id)
    db.session.add(b)
    db.session.commit()
    db.session.add(Booking(user_id=u.id, trek_id=t.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    b.status = "Cancelled"
    db.session.commit()
    db.session.add(Booking(user_id=u.id, trek_id=t.id))
    db.session.commit()


def test_slots_cannot_go_negative_or_exceed_total(app):
    t = make_trek()
    t.available_slots = 3
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    t.available_slots = -1
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_invalid_enum_rejected(app):
    with pytest.raises(IntegrityError):
        make_trek(assigned_staff_id=None) if False else db.session.add(
            Trek(name="T", location="L", difficulty="Insane", duration_days=1, total_slots=1,
                 available_slots=1, start_date=date(2026, 1, 1), end_date=date(2026, 1, 1)))
        db.session.commit()


def test_foreign_keys_enforced(app):
    db.session.add(Booking(user_id=999, trek_id=999))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_staff_assignment(app):
    su = make_user("s@x.com", "staff")
    sp = StaffProfile(user_id=su.id)
    db.session.add(sp)
    db.session.commit()
    t = make_trek(assigned_staff_id=sp.id)
    assert t.staff.user.email == "s@x.com"
    assert sp.treks == [t]
