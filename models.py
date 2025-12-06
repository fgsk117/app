"""
Модели базы данных
TODO: может стоит потом разбить на несколько файлов, если будет много моделей
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(100), unique=True, nullable=False)
    salary = db.Column(db.Float, nullable=False)
    monthly_savings = db.Column(db.Float, nullable=False)
    current_savings = db.Column(db.Float, default=0.0)
    use_savings_calculation = db.Column(db.Boolean, default=False)
    
    # telegram штуки
    telegram_chat_id = db.Column(db.String(100))
    telegram_notifications = db.Column(db.Boolean, default=False)
    telegram_code = db.Column(db.String(32), unique=True)  # для подключения
    
    # настройки уведомлений (добавлено позже)
    notification_interval = db.Column(db.String(20), default='default')
    browser_notifications = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
    price_ranges = db.relationship('PriceRange', backref='user', lazy=True, cascade='all, delete-orphan')
    blacklist_categories = db.relationship('BlacklistCategory', backref='user', lazy=True, cascade='all, delete-orphan')
    purchases = db.relationship('Purchase', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.telegram_code:
            self.telegram_code = secrets.token_urlsafe(16)

    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'salary': self.salary,
            'monthly_savings': self.monthly_savings,
            'current_savings': self.current_savings,
            'use_savings_calculation': self.use_savings_calculation,
            'telegram_connected': bool(self.telegram_chat_id),
            'telegram_notifications': self.telegram_notifications,
            'telegram_code': self.telegram_code,
            'notification_interval': self.notification_interval,
            'browser_notifications': self.browser_notifications,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class PriceRange(db.Model):
    __tablename__ = 'price_ranges'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    min_price = db.Column(db.Float, nullable=False)
    max_price = db.Column(db.Float)
    cooling_days = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'cooling_days': self.cooling_days
        }


class BlacklistCategory(db.Model):
    __tablename__ = 'blacklist_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category
        }


class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    cooling_period_days = db.Column(db.Integer, nullable=False)
    cooling_end_date = db.Column(db.DateTime, nullable=False)
    is_blacklisted = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    product_url = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    notifications = db.relationship('Notification', backref='purchase', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'category': self.category,
            'status': self.status,
            'cooling_period_days': self.cooling_period_days,
            'cooling_end_date': self.cooling_end_date.isoformat(),
            'is_blacklisted': self.is_blacklisted,
            'notes': self.notes,
            'product_url': self.product_url,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat()
        }


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # reminder_7, reminder_3, reminder_1, reminder_0, daily, weekly
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivered = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'purchase_id': self.purchase_id,
            'notification_type': self.notification_type,
            'sent_at': self.sent_at.isoformat(),
            'delivered': self.delivered,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }