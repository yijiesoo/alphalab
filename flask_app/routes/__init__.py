"""
Authentication routes: Login, Signup, Logout
"""
from functools import wraps

import requests
from flask import Blueprint, redirect, render_template, request, session, url_for

from ..config import Config

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# =====================================================================
# Auth Decorator
# =====================================================================
def login_required(f):
    """Decorator to require login (Flask session based)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


# =====================================================================
# Login Route
# =====================================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page with form"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="Email and password are required")

        try:
            # Use Firebase REST API to sign in
            api_key = Config.FIREBASE_WEB_API_KEY
            if not api_key:
                return render_template("login.html", error="Firebase not configured")

            response = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
                json={"email": email, "password": password, "returnSecureToken": True}
            )

            if response.status_code == 200:
                data = response.json()
                firebase_uid = data.get("localId")
                email = data.get("email")

                # Store user info in Flask session
                session["user_email"] = email
                session["firebase_uid"] = firebase_uid
                session["id_token"] = data.get("idToken")
                session.permanent = True

                # Add user to Supabase if available
                try:
                    from services.supabase_service import sync_user_to_supabase
                    sync_user_to_supabase(email, firebase_uid)
                except Exception as e:
                    print(f"⚠️  Could not sync user to Supabase: {e}")

                return redirect(url_for("dashboard.home"))
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Invalid credentials")
                return render_template("login.html", error=error_msg)
        except Exception as e:
            return render_template("login.html", error=f"Login error: {str(e)}")

    # If already logged in, redirect to home
    if "user_email" in session:
        return redirect(url_for("dashboard.home"))

    return render_template("login.html")


# =====================================================================
# Signup Route
# =====================================================================
@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup page with form"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # Validation
        if not email or not password or not password_confirm:
            return render_template("signup.html", error="All fields are required")

        if password != password_confirm:
            return render_template("signup.html", error="Passwords do not match")

        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters")

        try:
            # Create user with Firebase REST API
            api_key = Config.FIREBASE_WEB_API_KEY
            if not api_key:
                return render_template("signup.html", error="Firebase not configured")

            response = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}",
                json={"email": email, "password": password, "returnSecureToken": True}
            )

            if response.status_code == 200:
                data = response.json()
                firebase_uid = data.get("localId")
                email = data.get("email")

                # Auto-login after signup
                session["user_email"] = email
                session["firebase_uid"] = firebase_uid
                session["id_token"] = data.get("idToken")
                session.permanent = True

                # Add user to Supabase
                try:
                    from services.supabase_service import sync_user_to_supabase
                    sync_user_to_supabase(email, firebase_uid, is_new=True)
                except Exception as e:
                    print(f"⚠️  Could not create user in Supabase: {e}")

                return redirect(url_for("dashboard.home"))
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Signup failed")
                return render_template("signup.html", error=error_msg)
        except Exception as e:
            return render_template("signup.html", error=f"Signup error: {str(e)}")

    # If already logged in, redirect to home
    if "user_email" in session:
        return redirect(url_for("dashboard.home"))

    return render_template("signup.html")


# =====================================================================
# Logout Route
# =====================================================================
@auth_bp.route("/logout")
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for("auth.login"))
