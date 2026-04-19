import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from extensions import db, login_manager
from models import User, Item

from PIL import Image
import imagehash

load_dotenv()

# ---------------- APP SETUP ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_secret')

db_uri = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------- HELPERS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def handle_image_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique = f"{int(time.time())}_{filename}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], unique)
        file.save(path)

        try:
            with Image.open(path) as img:
                img_hash = str(imagehash.whash(img))
        except:
            img_hash = None

        return unique, img_hash

    return None, None


# ---------------- MATCHING (SAFE VERSION) ----------------
def check_for_match(new_item):

    try:
        opposite = 'found' if new_item.type == 'lost' else 'lost'

        candidates = Item.query.filter_by(
            type=opposite,
            status='open',
            category=new_item.category
        ).all()

        HASH_THRESHOLD = 20

        for candidate in candidates:

            match_found = None

            # ---- IMAGE MATCH ----
            if new_item.image_hash and candidate.image_hash:
                try:
                    h1 = imagehash.hex_to_hash(new_item.image_hash)
                    h2 = imagehash.hex_to_hash(candidate.image_hash)

                    if (h1 - h2) <= HASH_THRESHOLD:
                        match_found = candidate
                except:
                    pass

            # ---- LOCATION MATCH (SAFE NULL CHECK) ----
            if not match_found:
                if new_item.location and candidate.location:
                    if new_item.location.strip().lower() == candidate.location.strip().lower():
                        match_found = candidate

            # ---- APPLY MATCH ----
            if match_found:
                match_found.status = 'matched'
                new_item.status = 'matched'

                match_found.matched_with_id = new_item.id
                new_item.matched_with_id = match_found.id

                db.session.commit()

                flash(f'Match found for "{new_item.title}"!')
                return True

        return False

    except Exception as e:
        print("MATCH ERROR:", e)
        return False


# ---------------- ROUTES ----------------
@app.route('/')
def index():
    try:
        return render_template("index.html")
    except Exception as e:
        print("INDEX ERROR:", e)
        return "Server running", 200


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not re.match(r'^[a-zA-Z0-9.]+@kpriet\.ac\.in$', email):
            flash("Use official email")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("Already exists")
            return redirect(url_for('register'))

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template("auth.html", is_login=False)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))

        flash("Invalid login")
        return redirect(url_for('login'))

    return render_template("auth.html", is_login=True)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    items = Item.query.filter_by(user_id=current_user.id).all()

    stats = {
        "total": len(items),
        "lost": len([i for i in items if i.type == "lost"]),
        "found": len([i for i in items if i.type == "found"]),
        "matched": len([i for i in items if i.status == "matched"]),
        "resolved": len([i for i in items if i.status == "resolved"])
    }

    return render_template("dashboard.html", items=items, stats=stats)


@app.route('/report/<item_type>', methods=['GET', 'POST'])
@login_required
def report_item(item_type):

    if request.method == 'POST':

        date_str = request.form.get('date')

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            date_obj = datetime.utcnow().date()

        filename, img_hash = handle_image_upload(request.files.get('image'))

        item = Item(
            title=request.form.get('title'),
            category=request.form.get('category'),
            description=request.form.get('description'),
            date=date_obj,
            location=request.form.get('location'),
            image_filename=filename,
            image_hash=img_hash,
            type=item_type,
            user_id=current_user.id
        )

        db.session.add(item)
        db.session.commit()

        check_for_match(item)

        flash("Report submitted")
        return redirect(url_for('dashboard'))

    return render_template("report.html", item_type=item_type)


# ---------------- RUN ----------------
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run()
