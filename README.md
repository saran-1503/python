# Found It! - College Lost & Found System

A modern, transparent, and user-friendly "College Lost & Found" web application for students and staff at **KPR Institute of Engineering and Technology (KPRIET)**.

## Features

- **User Authentication**: Secure registration using your official `@kpriet.ac.in` college email.
- **Lost and Found Reporting**: Detailed forms to report items with image uploads and campus-specific locations.
- **Search & Filtering**: Quick discovery of items by name, category, or specific campus block.
- **Personal Dashboard**: Track and manage your reports (Edit, Delete, and Mark as Resolved).
- **Matching System**: Automated notifications when a potential match is found for your lost item.
- **Admin Control**: Oversight tools to manage the community board and clean up old reports.

## Project Structure

- `app.py`: Main application logic and routes.
- `models.py`: Database schema for Users and Items.
- `seed_db.py`: Script to populate the app with realistic KPRIET sample data.
- `extensions.py`: Flask extensions configuration (SQLAlchemy, Login, Mail).
- `static/`: CSS, JS, and uploaded images.
- `templates/`: HTML5 templates with consistent glassmorphism design.

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd <project-folder>
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in your details:
   - Generate a `SECRET_KEY`.
   - Provide `MAIL_USERNAME` and `MAIL_PASSWORD` for automated matching notifications.

5. **Seed the Database**:
   Populate the app with KPRIET sample users and items:
   ```bash
   python seed_db.py
   ```

6. **Run the Application**:
   ```bash
   python app.py
   ```
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Tech Stack

- **Backend**: Python (Flask)
- **Database**: SQLite (SQLAlchemy)
- **Frontend**: HTML5, Vanilla CSS, Javascript
- **Design Style**: Glassmorphism / Modern Inter-UI

## Deployment (Render & GitHub)

To make your website public:

1. **GitHub Setup**:
   - Create a new repository on GitHub (Private or Public).
   - In your local terminal, run:
     ```bash
     git init
     git add .
     git commit -m "Initial commit for deployment"
     git remote add origin <your-github-repo-url>
     git branch -M main
     git push -u origin main
     ```

2. **Render Setup**:
   - Go to [Dashboard.render.com](https://dashboard.render.com/) and click **New > Blueprint**.
   - Connect your GitHub repository.
   - Render will automatically detect `render.yaml` and set up the Web Service + PostgreSQL database.
   - **Environment Variables**: In the Render dashboard for your Web Service, go to **Environment** and add the following keys from your local `.env`:
     - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`
     - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_DISCOVERY_URL`

3. **Database Initialization**:
   - Once deployed, you can seed the initial KPRIET data by connecting to the Render Shell and running:
     ```bash
     python seed_db.py
     ```

4. **Update Google OAuth**:
   - Once your app is live (e.g., `https://kpriet-lost-found.onrender.com`), copy that URL.
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Update your **Authorized Redirect URIs** to: `https://your-app-name.onrender.com/authorize`.

