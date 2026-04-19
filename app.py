import os
import re
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure Logging (Render captures stdout)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Third-party Flask extensions
from flask import Flask, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Project-specific imports
from extensions import db, login_manager
from models import User, Item

# Image processing for visual matching
from PIL import Image
import imagehash
import cv2
import numpy as np

# Load environment variables from .env file
load_dotenv()

# --- APPLICATION SETUP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

# Configure Database (PostgreSQL for Render, SQLite for Local)
db_uri = os.getenv('DATABASE_URL')
if db_uri:
    # Handle the 'postgres://' vs 'postgresql://' issue
    if db_uri.startswith('postgres://'):
        db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
    
    # Render's PostgreSQL REQUIRES sslmode=require
    if 'sslmode' not in db_uri:
        separator = '&' if '?' in db_uri else '?'
        db_uri += f"{separator}sslmode=require"
else:
    # Fallback for local development
    db_uri = 'sqlite:///database.db'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Image Uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload directory exists (Critical for Render/Gunicorn)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create tables if they don't exist
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"DATABASE ERROR ON STARTUP: {str(e)}")
        # We don't exit here so the /health route can still work for debugging

@app.route('/health')
def health():
    """Diagnostic route to verify the app is running without database dependency."""
    return {
        "status": "alive",
        "database": str(app.config['SQLALCHEMY_DATABASE_URI'].split('@')[-1]), # Show host only for safety
        "time": datetime.utcnow().isoformat()
    }

@login_manager.user_loader
def load_user(user_id):
    """How Flask-Login finds our user in the database."""
    return User.query.get(int(user_id))

def allowed_file(filename):
    """Check if the uploaded file has a valid image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def calculate_feature_match_score(img1_path, img2_path):
    """
    Uses SIFT (Scale-Invariant Feature Transform) and RANSAC Homography 
    to verify geometric consistency between two images.
    Returns the number of inlier matches found.
    """
    try:
        # Load images in grayscale
        img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
        
        if img1 is None or img2 is None:
            return 0

        # Preprocessing: Resize to standard size for consistent feature density
        def resize_img(img, max_dim=800):
            h, w = img.shape
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                return cv2.resize(img, (int(w * scale), int(h * scale)))
            return img

        img1 = resize_img(img1)
        img2 = resize_img(img2)

        # Initialize SIFT detector with highly sensitive parameters
        sift = cv2.SIFT_create(contrastThreshold=0.01, edgeThreshold=15)

        # Find the keypoints and descriptors with SIFT
        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)

        if des1 is None or des2 is None or len(kp1) < 5 or len(kp2) < 5:
            return 0

        # FLANN parameters for SIFT
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
        search_params = dict(checks=50)
        
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        # Apply Low's ratio test (0.7 is robust)
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)

        # RANSAC Homography Check
        # We need at least 4 matches to find a homography.
        if len(good_matches) >= 5:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

            # Find homography with RANSAC
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if mask is not None:
                inliers = int(np.sum(mask))
                return inliers
        
        # Fallback for small images or few features
        return len(good_matches) // 2
    except Exception as e:
        print(f"Error in feature matching: {e}")
        return 0

def check_for_match(new_item):
    """
    Search for items of the opposite type that have the same category.
    Matches if:
    1. Location matches (case-insensitive) OR
    2. Photos resemble each other (low Hamming distance between pHashes) OR
    3. Photos share Geometric Feature Inliers (SIFT + RANSAC)
    """
    opposite_type = 'found' if new_item.type == 'lost' else 'lost'
    
    # 1. Search for potential candidates (same type and category)
    candidates = Item.query.filter_by(type=opposite_type, status='open') \
                           .filter(Item.category == new_item.category).all()
    
    match_found = None
    
    # Matching Thresholds
    HASH_THRESHOLD = 20    # Relaxed pHash threshold for better matching
    FEATURE_THRESHOLD = 4  # Minimum SIFT inliers for a confirmed geometric match

    for candidate in candidates:
        # 1. Primary Check: Image Similarity
        if new_item.image_filename and candidate.image_filename:
            # A. Fast Check: Hashing (captures global similarity)
            if new_item.image_hash and candidate.image_hash:
                try:
                    hash1 = imagehash.hex_to_hash(new_item.image_hash)
                    hash2 = imagehash.hex_to_hash(candidate.image_hash)
                    if (hash1 - hash2) <= HASH_THRESHOLD:
                        match_found = candidate
                        break
                except:
                    pass
            
            # B. Deep Check: Feature Matching (captures partial resemblance/rotation/background change)
            img1_path = os.path.join(app.config['UPLOAD_FOLDER'], new_item.image_filename)
            img2_path = os.path.join(app.config['UPLOAD_FOLDER'], candidate.image_filename)
            
            if os.path.exists(img1_path) and os.path.exists(img2_path):
                inlier_score = calculate_feature_match_score(img1_path, img2_path)
                if inlier_score >= FEATURE_THRESHOLD:
                    match_found = candidate
                    break
        
        # 2. Fallback Check: Location (only if no images or no image match)
        if candidate.location.strip().lower() == new_item.location.strip().lower():
            match_found = candidate
            break

    if match_found:
        # Link the items together
        match_found.status = 'matched'
        new_item.status = 'matched'
        match_found.matched_with_id = new_item.id
        new_item.matched_with_id = match_found.id
        
        db.session.commit()
        from flask import has_request_context
        if has_request_context():
            flash(f'A potential match for "{new_item.title}" was found! Check your dashboard for contact details.')
        return True
    
    return False


@app.route('/')
def index():
    recent_lost = Item.query.filter(Item.type == 'lost', Item.status != 'resolved').order_by(Item.created_at.desc()).limit(4).all()
    recent_found = Item.query.filter(Item.type == 'found', Item.status != 'resolved').order_by(Item.created_at.desc()).limit(4).all()
    return render_template('index.html', recent_lost=recent_lost, recent_found=recent_found)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 1. Enforce official college email domain
        if not re.match(r'^[a-zA-Z0-9.]+@kpriet\.ac\.in$', email):
            flash('Please use your official @kpriet.ac.in email.')
            return redirect(url_for('register'))
            
        # 2. Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('register'))
            
        # 3. Create and save the new user
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))

    return render_template('auth.html', is_login=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
            
        flash('Invalid email or password.')
        return redirect(url_for('login'))

    return render_template('auth.html', is_login=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))




def handle_image_upload(file):
    """Saves the uploaded image and returns (unique_filename, image_hash)."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Generate wavelet hash for robust visual matching
        try:
            with Image.open(filepath) as img:
                img_hash = str(imagehash.whash(img)) # Using whash for better partial/background resilience
        except Exception as e:
            print(f"Error generating image hash: {e}")
            img_hash = None
            
        return unique_filename, img_hash
    return None, None

@app.route('/report/<item_type>', methods=['GET', 'POST'])
@login_required
def report_item(item_type):
    """Handles reporting a lost or found item."""
    if item_type not in ['lost', 'found']:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # 1. Collect data from the form
        date_str = request.form.get('date')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            date_obj = datetime.utcnow().date()
            
        # 2. Handle image upload if present
        filename, img_hash = handle_image_upload(request.files.get('image'))
                
        # 3. Create the new item record
        new_item = Item(
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
        db.session.add(new_item)
        db.session.commit()
        
        # 4. Check if this report matches an existing one
        check_for_match(new_item)
        
        flash('Report submitted successfully!')
        return redirect(url_for('items', type=item_type))
        
    return render_template('report.html', item_type=item_type)

@app.route('/items')
def items():
    """Route to browse and search for lost or found items."""
    # Get search parameters from the URL
    q_type = request.args.get('type')           # 'lost' or 'found'
    q_search = request.args.get('search', '')    # Keyword search
    q_category = request.args.get('category')   # Category filter
    q_location = request.args.get('location')   # Location filter
    
    # Show all items that are not yet resolved
    query = Item.query.filter(Item.status != 'resolved')
    
    # Apply filters based on what the user provided
    if q_type in ['lost', 'found']:
        query = query.filter_by(type=q_type)
        
    if q_search:
        search_filter = f'%{q_search}%'
        query = query.filter(Item.title.ilike(search_filter) | Item.description.ilike(search_filter))
        
    if q_category:
        query = query.filter_by(category=q_category)
        
    if q_location:
        query = query.filter_by(location=q_location)
        
    # Get results, newest first
    result_items = query.order_by(Item.created_at.desc()).all()
    
    return render_template('items.html', items=result_items, list_type=q_type)

@app.route('/item/<int:id>')
def item_detail(id):
    item = Item.query.get_or_404(id)
    return render_template('item_detail.html', item=item)



@app.route('/item/delete/<int:id>')
@login_required
def delete_item(id):
    """Allows a user to delete their own reported item."""
    item = Item.query.get_or_404(id)
    
    # Security Check: Only the person who reported the item can delete it
    if item.user_id != current_user.id:
        flash('You do not have permission to delete this item.')
        return redirect(url_for('dashboard'))
        
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    stats = {
        'total': len(user_items),
        'lost': len([i for i in user_items if i.type == 'lost']),
        'found': len([i for i in user_items if i.type == 'found']),
        'resolved': len([i for i in user_items if i.status == 'resolved']),
        'matched': len([i for i in user_items if i.status == 'matched'])
    }

    return render_template('dashboard.html', items=user_items, stats=stats)

@app.route('/item/resolve/<int:id>')
@login_required
def resolve_item(id):
    item = Item.query.get_or_404(id)
    if item.user_id != current_user.id:
        flash('You do not have permission to modify this item.')
        return redirect(url_for('dashboard'))
    
    item.status = 'resolved'
    db.session.commit()
    flash(f'Item "{item.title}" marked as resolved!')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
