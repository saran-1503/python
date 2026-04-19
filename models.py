from extensions import db
from flask_login import UserMixin
from datetime import datetime

# User table to store student and admin information
class User(UserMixin, db.Model):
    """
    Represents a user in the system (Student or Admin).
    Inherits from UserMixin to work easily with Flask-Login.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False) # Must be @kpriet.ac.in
    password_hash = db.Column(db.String(200), nullable=True)     # Hashed for security

    # One user can have many items (Lost or Found)
    items = db.relationship('Item', backref='author', lazy=True)

# Item table to store Lost and Found reports
class Item(db.Model):
    """
    Represents an item reported as lost or found.
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)      # e.g., Electronics, Books
    description = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=False)                # Date when lost/found
    location = db.Column(db.String(100), nullable=False)    # Where it happened
    image_filename = db.Column(db.String(200), nullable=True) # Path to uploaded image
    image_hash = db.Column(db.String(64), nullable=True)     # Perceptual hash for visual matching
    
    # 'type' tells us if it's a 'lost' report or a 'found' report
    type = db.Column(db.String(10), nullable=False) 
    
    # 'status' tracks if it's 'open', 'resolved', or 'matched'
    status = db.Column(db.String(20), default='open') 
    
    # Matching logic: links a lost item to a found item
    matched_with_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship for matching logic inside the database
    matched_item = db.relationship('Item', remote_side=[id], post_update=True)

