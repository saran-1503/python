import os
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, Item

def seed_database():
    """
    Resets the database and populates it with sample users and items.
    This is useful for showing how the application looks with data.
    """
    with app.app_context():
        # 1. Reset the database (Delete everything and start fresh)
        print("Resetting database...")
        db.drop_all()
        db.create_all()

        # 2. Create sample student users
        print("Creating sample students...")
        students_data = [
            ("Saran Kumar", "21cs145@kpriet.ac.in"),
            ("Priya Dharshini", "22ec012@kpriet.ac.in"),
            ("Rahul Raj", "20me088@kpriet.ac.in"),
            ("Anita Mary", "23ai005@kpriet.ac.in")
        ]

        user_list = []
        for name, email in students_data:
            user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash("password123", method='pbkdf2:sha256')
            )
            db.session.add(user)
            user_list.append(user)
        
        # Save users first so they get IDs
        db.session.commit()

        # 4. Define sample locations and categories
        locations = ["Library", "Food Court", "Mechanical Block", "AI & DS Block", "Hostel"]
        categories = ["Electronics", "Books", "Accessories", "Wallets", "Other"]

        # 5. Create sample items (Lost and Found)
        print("Creating sample items...")
        
        # Data for lost items
        lost_data = [
            ("iPhone 13", "Electronics", "Blue color, back cracked"),
            ("Physics Book", "Books", "Semester 4 textbook"),
            ("Casio Watch", "Accessories", "Silver metal strap"),
            ("House Keys", "Other", "3 keys with red keychain")
        ]

        # Data for found items
        found_data = [
            ("Laptop Charger", "Electronics", "Dell 65W charger"),
            ("Leather Wallet", "Wallets", "Brown color, found near library"),
            ("Water Bottle", "Other", "Blue Milton bottle"),
            ("Spectacles", "Accessories", "Black frame")
        ]

        # Function to add items to database
        def add_items(data_list, item_type):
            for title, cat, desc in data_list:
                item = Item(
                    title=title,
                    category=cat,
                    description=desc,
                    location=random.choice(locations),
                    date=(datetime.utcnow() - timedelta(days=random.randint(1, 5))).date(),
                    type=item_type,
                    user_id=random.choice(user_list).id
                )
                db.session.add(item)

        add_items(lost_data, "lost")
        add_items(found_data, "found")

        # 6. Final save to database
        db.session.commit()
        print("Database seeded successfully!")

if __name__ == '__main__':
    seed_database()
