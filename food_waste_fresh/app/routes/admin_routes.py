from flask import Blueprint, render_template, session, redirect, url_for, request
from datetime import datetime, timedelta

from db import get_connection
from app.utils.notifications import add_notification

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# =========================
# DASHBOARD
# =========================
@admin_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    conn = get_connection()
    cur = conn.cursor()

    # USERS
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE role='donor'")
    donors = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE role='ngo'")
    ngos = cur.fetchone()[0]

    # DONATIONS
    cur.execute("SELECT COUNT(*) FROM donations")
    total_donations = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM donations WHERE status='Completed'")
    completed = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM donations
        WHERE status IN ('Pending','Accepted')
    """)
    pending_pickups = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM donations
        WHERE status IN ('Pending','Accepted')
        AND expiry_time < NOW()
    """)
    critical_flags = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        donors=donors,
        ngos=ngos,
        total_donations=total_donations,
        completed=completed,
        pending_pickups=pending_pickups,
        critical_flags=critical_flags
    )


# =========================
# USERS
# =========================
@admin_bp.route('/users')
def users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    role_filter = request.args.get('role')
    search = request.args.get('search')

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT id, full_name, email, role, created_at
        FROM users
        WHERE 1=1
    """
    params = []

    if role_filter:
        query += " AND role = %s"
        params.append(role_filter)

    if search:
        query += " AND (full_name LIKE %s OR email LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY created_at DESC"

    cur.execute(query, tuple(params))
    users_data = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'admin/users.html',
        users=users_data,
        role_filter=role_filter,
        search=search
    )


# =========================
# TOGGLE USER
# =========================
@admin_bp.route('/users/toggle/<int:user_id>')
def toggle_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET status = IF(status='Active','Disabled','Active')
        WHERE id=%s AND role!='admin'
    """, (user_id,))

    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('admin.users'))


# =========================
# DONATIONS
# =========================
@admin_bp.route('/donations')
def donations():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    status_filter = request.args.get('status')
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT d.id, d.food_title, d.quantity_kg, d.status, d.created_at,
               u.full_name AS donor_name
        FROM donations d
        JOIN users u ON d.donor_id = u.id
        WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND d.status = %s"
        params.append(status_filter)

    if start_date and end_date:
        query += " AND DATE(d.created_at) BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    if search:
        query += " AND (d.food_title LIKE %s OR u.full_name LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY d.created_at DESC"

    cur.execute(query, tuple(params))
    donations_data = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'admin/donations.html',
        donations=donations_data,
        status_filter=status_filter,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
