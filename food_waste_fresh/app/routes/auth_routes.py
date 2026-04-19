from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_connection   # ✅ FIXED

auth_bp = Blueprint('auth', __name__)


# =========================
# LANDING
# =========================
@auth_bp.route('/')
def landing():
    return render_template('landing.html')


# =========================
# REGISTER
# =========================
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        hashed_password = generate_password_hash(password)

        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO users (full_name, email, password, role)
                VALUES (%s, %s, %s, %s)
            """, (full_name, email, hashed_password, role))

            conn.commit()
            flash("Account created successfully. Please login.", "success")
            return redirect(url_for('auth.login'))

        except Exception as e:
            conn.rollback()
            flash("Email already registered or error occurred.", "danger")

        finally:
            cur.close()
            conn.close()

    return render_template('auth/register.html')


# =========================
# LOGIN
# =========================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, full_name, password, role
            FROM users
            WHERE email=%s
        """, (email,))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['role'] = user[3]

            if user[3] == 'donor':
                return redirect(url_for('donor.dashboard'))
            elif user[3] == 'ngo':
                return redirect(url_for('ngo.dashboard'))
            elif user[3] == 'admin':
                return redirect(url_for('admin.dashboard'))

            return redirect(url_for('auth.landing'))

        flash("Invalid email or password", "danger")

    return render_template('auth/login.html')


# =========================
# LOGOUT
# =========================
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.landing'))
