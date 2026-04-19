from flask import Blueprint, render_template, session, redirect, url_for, flash, request, send_file
from app.models.db import mysql
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

import io
import urllib.request

ngo_bp = Blueprint('ngo', __name__, url_prefix='/ngo')


# =========================
# DASHBOARD
# =========================
@ngo_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM donations WHERE status='Pending'")
    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM donations
        WHERE accepted_by=%s
    """, (session['user_id'],))
    accepted = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM donations
        WHERE accepted_by=%s AND status='Picked'
    """, (session['user_id'],))
    picked = cur.fetchone()[0]

    cur.close()

    return render_template(
        'ngo/dashboard.html',
        pending=pending,
        accepted=accepted,
        picked=picked
    )


# =========================
# DISTANCE FUNCTION
# =========================
def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


# =========================
# AVAILABLE DONATIONS (AI SORT)
# =========================
@ngo_bp.route('/available-donations')
def available_donations():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return redirect(url_for('auth.login'))

    NGO_LAT, NGO_LNG = 19.0760, 72.8777

    city = request.args.get('city', '')
    urgency = request.args.get('urgency', '')
    max_hours = request.args.get('max_hours', '')
    sort_by = request.args.get('sort_by', 'ai')

    query = """
        SELECT id, food_title, quantity_kg, city, urgency,
               expiry_time, packaging_condition,
               latitude, longitude
        FROM donations
        WHERE status='Pending'
    """
    params = []

    if city:
        query += " AND city=%s"
        params.append(city)

    if urgency:
        query += " AND urgency=%s"
        params.append(urgency)

    cur = mysql.connection.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()

    now = datetime.now()
    results = []

    for r in rows:
        expiry = r[5]
        hours_left = (expiry - now).total_seconds() / 3600 if expiry else 999

        if max_hours and hours_left > float(max_hours):
            continue

        distance_km = None
        if r[7] and r[8]:
            distance_km = calculate_distance(NGO_LAT, NGO_LNG, float(r[7]), float(r[8]))

        score = 0

        # urgency score
        score += 50 if r[4] == 'Immediate' else 30 if r[4] == 'High' else 10

        # expiry score
        if hours_left <= 2:
            score += 40
        elif hours_left <= 6:
            score += 25
        elif hours_left <= 12:
            score += 10

        # condition
        if r[6] == 'Good':
            score += 15

        # distance score
        if distance_km:
            score += 25 if distance_km <= 5 else 15 if distance_km <= 10 else 0

        results.append({
            "data": r,
            "score": score,
            "hours_left": round(hours_left, 1),
            "distance": round(distance_km, 1) if distance_km else None
        })

    if sort_by == 'distance':
        results.sort(key=lambda x: x["distance"] if x["distance"] else 999)
    elif sort_by == 'expiry':
        results.sort(key=lambda x: x["hours_left"])
    else:
        results.sort(key=lambda x: x["score"], reverse=True)

    return render_template(
        'ngo/available_donations.html',
        donations=results,
        city=city,
        urgency=urgency,
        max_hours=max_hours,
        sort_by=sort_by
    )


# =========================
# ACCEPT DONATION
# =========================
@ngo_bp.route('/accept-donation/<int:donation_id>')
def accept_donation(donation_id):
    if 'user_id' not in session or session.get('role') != 'ngo':
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT full_name FROM users WHERE id=%s", (session['user_id'],))
    ngo = cur.fetchone()
    ngo_name = ngo[0] if ngo else "Unknown NGO"

    cur.execute("SELECT donor_id FROM donations WHERE id=%s", (donation_id,))
    result = cur.fetchone()

    if not result:
        cur.close()
        return "Donation not found", 404

    donor_id = result[0]

    cur.execute("""
        UPDATE donations
        SET status='Accepted',
            accepted_by=%s,
            accepted_at=NOW()
        WHERE id=%s AND status='Pending'
    """, (session['user_id'], donation_id))

    mysql.connection.commit()

    cur.execute("SELECT full_name FROM users WHERE id=%s", (donor_id,))
    donor = cur.fetchone()
    donor_name = donor[0] if donor else "User"

    cur.execute("""
        INSERT INTO notifications (user_id, message, type)
        VALUES (%s, %s, %s)
    """, (
        donor_id,
        f"Dear {donor_name}, your donation was accepted by {ngo_name}",
        "success"
    ))

    mysql.connection.commit()
    cur.close()

    return render_template('ngo/accept_success.html', donation_id=donation_id)
