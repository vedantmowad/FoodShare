from flask import Blueprint, render_template, session, redirect, url_for,request
from datetime import datetime, timedelta
from app.models.db import mysql
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
from app.utils.notifications import add_notification
from db import get_connection

conn = get_connection()
cursor = conn.cursor()
@admin_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()

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

    # CRITICAL FLAGS (expired but not picked)
    cur.execute("""
        SELECT COUNT(*) FROM donations
        WHERE status IN ('Pending','Accepted')
        AND expiry_time < NOW()
    """)
    critical_flags = cur.fetchone()[0]

    cur.close()

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

from flask import request, redirect, url_for, session, render_template

@admin_bp.route('/users')
def users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    role_filter = request.args.get('role')
    search = request.args.get('search')

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

    cur = mysql.connection.cursor()
    cur.execute(query, tuple(params))
    users = cur.fetchall()
    cur.close()

    return render_template(
        'admin/users.html',
        users=users,
        role_filter=role_filter,
        search=search
    )




@admin_bp.route('/users/toggle/<int:user_id>')
def toggle_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE users
        SET status = IF(status='Active','Disabled','Active')
        WHERE id=%s AND role!='admin'
    """, (user_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('admin.users'))


@admin_bp.route('/donations')
def donations():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    status_filter = request.args.get('status')
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = """
        SELECT 
            d.id,
            d.food_title,
            d.quantity_kg,
            d.status,
            d.created_at,
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

    cur = mysql.connection.cursor()
    cur.execute(query, tuple(params))
    donations = cur.fetchall()
    cur.close()

    return render_template(
        'admin/donations.html',
        donations=donations,
        status_filter=status_filter,
        search=search,
        start_date=start_date,
        end_date=end_date
    )

@admin_bp.route('/reports')
def reports():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    date_filter = ""
    params = []

    if start_date and end_date:
        date_filter = " WHERE DATE(created_at) BETWEEN %s AND %s"
        params = [start_date, end_date]

    cur = mysql.connection.cursor()

    # -------- KPIs --------
    cur.execute(f"""
        SELECT
            COUNT(*) AS total,
            SUM(quantity_kg) AS total_kg,
            SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status='Cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM donations
        {date_filter}
    """, tuple(params))

    total, total_kg, completed, pending, cancelled = cur.fetchone()

    total = total or 0
    total_kg = total_kg or 0
    completed = completed or 0
    pending = pending or 0
    cancelled = cancelled or 0

    completion_rate = round((completed / total) * 100, 1) if total else 0
    avg_qty = round((total_kg / total), 2) if total else 0

    # -------- STATUS BREAKDOWN --------
    cur.execute(f"""
        SELECT status, COUNT(*)
        FROM donations
        {date_filter}
        GROUP BY status
    """, tuple(params))
    status_rows = cur.fetchall()

    status_labels = [row[0] for row in status_rows]
    status_counts = [row[1] for row in status_rows]

    # -------- DAILY TREND --------
    cur.execute(f"""
        SELECT DATE(created_at), COUNT(*)
        FROM donations
        {date_filter}
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
    """, tuple(params))
    daily_rows = cur.fetchall()

    daily_labels = [str(row[0]) for row in daily_rows]
    daily_counts = [row[1] for row in daily_rows]

    # -------- TOP DONORS --------
    cur.execute(f"""
        SELECT u.full_name, COUNT(d.id), SUM(d.quantity_kg)
        FROM donations d
        JOIN users u ON d.donor_id = u.id
        {date_filter.replace("created_at", "d.created_at")}
        GROUP BY d.donor_id
        ORDER BY SUM(d.quantity_kg) DESC
        LIMIT 5
    """, tuple(params))
    top_donors = cur.fetchall()

    # -------- RECENT DONATIONS --------
    cur.execute("""
        SELECT food_title, quantity_kg, status, created_at
        FROM donations
        ORDER BY created_at DESC
        LIMIT 10
    """)
    recent = cur.fetchall()

    cur.close()

    return render_template(
        'admin/reports.html',
        total=total,
        total_kg=total_kg,
        completed=completed,
        pending=pending,
        cancelled=cancelled,
        completion_rate=completion_rate,
        avg_qty=avg_qty,
        status_labels=status_labels,
        status_counts=status_counts,
        daily_labels=daily_labels,
        daily_counts=daily_counts,
        top_donors=top_donors,
        recent=recent,
        start_date=start_date,
        end_date=end_date
    )


@admin_bp.route('/prediction')
def prediction():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()

    # =============================
    # 1. FETCH DATA (30 DAYS)
    # =============================
    cur.execute("""
        SELECT 
            DATE(created_at) as d, 
            COUNT(*) as count, 
            SUM(quantity_kg) as kg,
            COUNT(DISTINCT donor_id) as donors
        FROM donations
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY DATE(created_at)
        ORDER BY d ASC
    """)
    daily_data = cur.fetchall()  # List of tuples: (date, count, kg, unique_donors_daily)

    # Process Data in Python (Easier for complex stats)
    total_donations = sum(d[1] for d in daily_data)
    total_kg = sum(d[2] or 0 for d in daily_data)

    # Get total unique donors over the whole period
    cur.execute("""
        SELECT COUNT(DISTINCT donor_id) FROM donations 
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """)
    unique_donors = cur.fetchone()[0] or 0

    # =============================
    # 2. STATISTICAL ANALYSIS
    # =============================
    active_days = len(daily_data)
    daily_counts = [d[1] for d in daily_data]

    avg_daily = round(total_donations / 30, 2)
    avg_kg_per_day = round(total_kg / 30, 2)

    # Variance Calculation
    if daily_counts:
        variance = sum((x - avg_daily) ** 2 for x in daily_counts) / 30
    else:
        variance = 0

    stability_score = 100 - (variance * 10)  # Simple heuristic: lower variance = higher score
    stability_score = max(0, min(100, stability_score))  # Clamp between 0-100

    # =============================
    # 3. TREND DETECTION (Last 7 days vs Previous 7 days)
    # =============================
    # Filter list for last 7 days and previous 7
    today = datetime.now().date()
    last_7 = [d[1] for d in daily_data if d[0] >= today - timedelta(days=7)]
    prev_7 = [d[1] for d in daily_data if today - timedelta(days=14) <= d[0] < today - timedelta(days=7)]

    sum_last_7 = sum(last_7)
    sum_prev_7 = sum(prev_7)

    trend_pct = 0
    if sum_prev_7 > 0:
        trend_pct = round(((sum_last_7 - sum_prev_7) / sum_prev_7) * 100, 1)

    # =============================
    # 4. HOURLY & DONOR INSIGHTS
    # =============================
    cur.execute("""
        SELECT HOUR(created_at), COUNT(*) FROM donations 
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY HOUR(created_at) ORDER BY COUNT(*) DESC LIMIT 1
    """)
    peak_row = cur.fetchone()
    peak_hour = peak_row[0] if peak_row else None

    # Top Donor Share
    cur.execute("""
        SELECT COUNT(*) FROM donations 
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) 
        GROUP BY donor_id ORDER BY COUNT(*) DESC LIMIT 1
    """)
    top_donor_row = cur.fetchone()
    top_donor_count = top_donor_row[0] if top_donor_row else 0
    top_donor_share = round((top_donor_count / total_donations * 100), 1) if total_donations else 0

    # =============================
    # 5. FORECAST GENERATION
    # =============================
    forecast = {
        "today": {
            "val": round(avg_daily),
            "kg": round(avg_kg_per_day, 1),
            "conf": "High" if active_days > 20 else "Low"
        },
        "week": {
            "val": round(avg_daily * 7),
            "kg": round(avg_kg_per_day * 7, 1)
        },
        "month": {
            "val": round(avg_daily * 30),
            "kg": round(avg_kg_per_day * 30, 1)
        }
    }

    # =============================
    # 6. INTELLIGENT ALERTS
    # =============================
    alerts = []
    if trend_pct < -15:
        alerts.append({"type": "danger", "msg": f"Donation volume dropped by {abs(trend_pct)}% this week."})
    if top_donor_share > 40:
        alerts.append({"type": "warning", "msg": f"High risk: One donor controls {top_donor_share}% of supply."})
    if stability_score < 50:
        alerts.append({"type": "info", "msg": "Supply is volatile. Keep buffer stock."})
    if not alerts:
        alerts.append({"type": "success", "msg": "System is running smoothly with stable supply."})

    cur.close()

    return render_template(
        'admin/prediction.html',
        forecast=forecast,
        avg_daily=avg_daily,
        avg_kg=avg_kg_per_day,
        trend_pct=trend_pct,
        stability_score=int(stability_score),
        peak_hour=peak_hour,
        top_donor_share=top_donor_share,
        unique_donors=unique_donors,
        alerts=alerts
    )

