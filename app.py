import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv

# Flask imports
from flask import Flask, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Project-specific imports
from extensions import db, login_manager
from models import User, Item

# Image processing
from PIL import Image
import imagehash
import cv2
import numpy as np

# Load environment variables
load_dotenv()

# --- APPLICATION SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

# Logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Database configuration
db_uri = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------- IMAGE FEATURE MATCHING ----------------
def calculate_feature_match_score(img1_path, img2_path):
    """
    SIFT + RANSAC based geometric matching
    Returns number of inlier matches
    """
    try:
        img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)

        if img1 is None or img2 is None:
            return 0

        def resize_img(img, max_dim=800):
            h, w = img.shape
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                return cv2.resize(img, (int(w * scale), int(h * scale)))
            return img

        img1 = resize_img(img1)
        img2 = resize_img(img2)

        sift = cv2.SIFT_create(contrastThreshold=0.01, edgeThreshold=15)

        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)

        if des1 is None or des2 is None or len(kp1) < 5 or len(kp2) < 5:
            return 0

        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)

        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        good_matches = []
        for pair in matches:
            if len(pair) == 2:
                m, n = pair
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)

        if len(good_matches) >= 5:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

            _, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

            if mask is not None:
                return int(np.sum(mask))

        return len(good_matches) // 2

    except Exception as e:
        print(f"Error in feature matching: {e}")
        return 0


# ---------------- MATCHING LOGIC ----------------
def check_for_match(new_item):

    opposite_type = 'found' if new_item.type == 'lost' else 'lost'

    candidates = Item.query.filter_by(
        type=opposite_type,
        status='open'
    ).filter(Item.category == new_item.category).all()

    HASH_THRESHOLD = 20
    FEATURE_THRESHOLD = 4

    for candidate in candidates:

        # ---- IMAGE MATCH ----
        if new_item.image_filename and candidate.image_filename:

            # Perceptual hash check
            if new_item.image_hash and candidate.image_hash:
                try:
                    hash1 = imagehash.hex_to_hash(new_item.image_hash)
                    hash2 = imagehash.hex_to_hash(candidate.image_hash)

                    if (hash1 - hash2) <= HASH_THRESHOLD:
                        match_found = candidate
                        break
                except:
                    pass

            # Feature-based check (FIXED INDENTATION HERE)
            img1_path = os.path.join(app.config['UPLOAD_FOLDER'], new_item.image_filename)
            img2_path = os.path.join(app.config['UPLOAD_FOLDER'], candidate.image_filename)

            inlier_score = 0

            if os.path.exists(img1_path) and os.path.exists(img2_path):
                # currently simplified (you can enable heavy CV later)
                inlier_score = 0

            if inlier_score >= FEATURE_THRESHOLD:
                match_found = candidate
                break

        # ---- LOCATION FALLBACK ----
        if candidate.location and new_item.location:
            if candidate.location.strip().lower() == new_item.location.strip().lower():
                match_found = candidate
                break

    else:
        return False

    # ---------------- LINK MATCH ----------------
    match_found.status = 'matched'
    new_item.status = 'matched'

    match_found.matched_with_id = new_item.id
    new_item.matched_with_id = match_found.id

    db.session.commit()

    if current_app:
        flash(f'A potential match for "{new_item.title}" was found!')

    return True


# ---------------- IMAGE UPLOAD ----------------
def handle_image_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        file.save(filepath)

        try:
            with Image.open(filepath) as img:
                img_hash = str(imagehash.whash(img))
        except:
            img_hash = None

        return unique_filename, img_hash

    return None, None


# ---------------- ROUTES ----------------
@app.route('/')
def index():
    recent_lost = Item.query.filter(
        Item.type == 'lost',
        Item.status != 'resolved'
    ).order_by(Item.created_at.desc()).limit(4).all()

    recent_found = Item.query.filter(
        Item.type == 'found',
        Item.status != 'resolved'
    ).order_by(Item.created_at.desc()).limit(4).all()

    return render_template('index.html', recent_lost=recent_lost, recent_found=recent_found)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not re.match(r'^[a-zA-Z0-9.]+@kpriet\.ac\.in$', email):
            flash('Use official college email.')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists.')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        user = User(name=name, email=email, password_hash=hashed_pw)

        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('auth.html', is_login=False)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Invalid credentials')
        return redirect(url_for('login'))

    return render_template('auth.html', is_login=True)


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
        'total': len(items),
        'lost': len([i for i in items if i.type == 'lost']),
        'found': len([i for i in items if i.type == 'found']),
        'matched': len([i for i in items if i.status == 'matched']),
        'resolved': len([i for i in items if i.status == 'resolved'])
    }

    return render_template('dashboard.html', items=items, stats=stats)


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
