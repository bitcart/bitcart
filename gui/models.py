from sqlalchemy.orm import relationship

from .db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, index=True)
    username = db.Column(db.String, index=True)
    email = db.Column(db.String, index=True)
    hashed_password = db.Column(db.String)
    is_superuser = db.Column(db.Boolean(), default=False)


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String(length=1000))
    xpub = db.Column(db.String(length=1000))
    balance = db.Column(db.Numeric())
    user_data = relationship("User")
    user = db.Column(db.Integer, db.ForeignKey('users.id'))
