from flask import Blueprint, render_template, session, redirect, url_for, request, flash, send_file, jsonify, current_app
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import io
from db import get_connection  # ✅ FIXED

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


donor_bp = Blueprint('donor', __name__, url_prefix='/donor')


# =========================
# DASHBOARD
# =========================
@donor_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('auth.login'))

    donor_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM donations WHERE donor_id=%s", (donor_id,))
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM donations 
        WHERE donor_id=%s AND status IN ('Picked','Completed')
    """, (donor_id,))
    picked = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM donations 
        WHERE donor_id=%s AND status='Pending'
    """, (donor_id,))
    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT SUM(quantity_kg) FROM donations 
        WHERE donor_id=%s AND status='Completed'
    """, (donor_id,))
    total_kg = cur.fetchone()[0] or 0

    people_fed = int(total_kg * 3)

    cur.close()
    conn.close()

    return render_template(
        'donor/dashboard.html',
        total=total,
        picked=picked,
        pending=pending,
        people_fed=people_fed
    )


# =========================
# ADD DONATION
# =========================
@donor_bp.route('/add-donation', methods=['GET', 'POST'])
def add_donation():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        conn = get_connection()
        cur = conn.cursor()

        donor_id = session['user_id']

        cur.execute("""
            INSERT INTO donations (
                donor_id, food_title, food_type, food_category,
                quantity_kg, servings, prepared_time, expiry_time,
                pickup_address, city, state, pincode,
                contact_name, contact_phone, special_instructions,
                packaging_condition, temperature_condition, hygiene_checked,
                pickup_start_time, pickup_end_time, urgency,
                pickup_type, accessibility_notes,
                latitude, longitude
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            donor_id,
            request.form['food_title'],
            request.form['food_type'],
            request.form['food_category'],
            request.form['quantity_kg'],
            request.form.get('servings'),
            request.form['prepared_time'],
            request.form['expiry_time'],
            request.form['pickup_address'],
            request.form['city'],
            request.form['state'],
            request.form['pincode'],
            request.form['contact_name'],
            request.form['contact_phone'],
            request.form.get('special_instructions'),
            request.form.get('packaging_condition'),
            request.form.get('temperature_condition'),
            1 if request.form.get('hygiene_checked') else 0,
            request.form.get('pickup_start_time'),
            request.form.get('pickup_end_time'),
            request.form.get('urgency'),
            request.form.get('pickup_type'),
            request.form.get('accessibility_notes'),
            request.form.get('latitude'),
            request.form.get('longitude')
        ))

        conn.commit()
        donation_id = cur.lastrowid

        cur.close()
        conn.close()

        return render_template('donor/donation_success.html', donation_id=donation_id)

    return render_template('donor/add_donation.html')


# =========================
# MY DONATIONS
# =========================
@donor_bp.route('/my-donations')
def my_donations():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('auth.login'))

    donor_id = session['user_id']

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, food_title, quantity_kg, city, expiry_time, status, created_at
        FROM donations
        WHERE donor_id=%s
        ORDER BY created_at DESC
    """, (donor_id,))

    donations = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('donor/my_donations.html', donations=donations)


# =========================
# CANCEL DONATION
# =========================
@donor_bp.route('/cancel-donation/<int:donation_id>')
def cancel_donation(donation_id):
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('auth.login'))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE donations
        SET status='Cancelled'
        WHERE id=%s AND donor_id=%s AND status='Pending'
    """, (donation_id, session['user_id']))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('donor.my_donations'))
