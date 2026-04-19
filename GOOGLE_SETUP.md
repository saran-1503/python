# Google OAuth Setup Guide

To enable "Sign in with Google," you must create a project in the Google Cloud Console and generate credentials.

## Step 1: Create a Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project** > **New Project**.
3. Name it `KPRIET-Lost-Found` and click **Create**.

## Step 2: Configure OAuth Consent Screen
1. In the sidebar, go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (unless you have a Google Workspace org, then select **Internal** if available).
3. Fill in:
   - **App name**: `KPRIET Lost & Found`
   - **User support email**: (Your admin email)
   - **Developer contact info**: (Your admin email)
4. Add the scope: `openid`, `https://www.googleapis.com/auth/userinfo.email`, and `https://www.googleapis.com/auth/userinfo.profile`.
5. Under **Test users**, add your own `@kpriet.ac.in` email to test while in development.

## Step 3: Create Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Select **Web application**.
4. **Authorized JavaScript origins**:
   - `http://localhost:5000`
5. **Authorized redirect URIs**:
   - `http://localhost:5000/authorize` (Very important!)
6. Click **Create**.

## Step 4: Update your .env
Copy the **Client ID** and **Client Secret** into your `.env` file:
```env
GOOGLE_CLIENT_ID=your_id_here
GOOGLE_CLIENT_SECRET=your_secret_here
GOOGLE_DISCOVERY_URL=https://accounts.google.com/.well-known/openid-configuration
```

## Step 5: Restart the App
Restart your Flask server to pick up the new environment variables.
