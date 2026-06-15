from flask_login import UserMixin
from datetime import datetime
from db import db

class User(UserMixin, db.Model):
    __tablename__ = 'Users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tracked_items = db.relationship('TrackedItem', backref='user', lazy=True)

class TrackedItem(db.Model):
    __tablename__ = 'TrackedItems'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(500))
    alert_mode = db.Column(db.String(20), default='absolute')
    alert_target = db.Column(db.Float, nullable=False)
    initial_price = db.Column(db.Float)
    current_price = db.Column(db.Float)
    lowest_price = db.Column(db.Float)
    highest_price = db.Column(db.Float)
    status = db.Column(db.String(20), default='active')
    consecutive_errors = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime)

    # Relationships
    price_history = db.relationship('PriceHistory', backref='item', lazy=True, cascade="all, delete-orphan")

class PriceHistory(db.Model):
    __tablename__ = 'PriceHistory'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('TrackedItems.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
