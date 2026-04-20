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
    
from flask import send_file
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
import io

@donor_bp.route('/download_receipt/<int:donation_id>')
def download_receipt(donation_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            d.id, u.full_name, d.food_title, d.food_type, d.food_category,
            d.quantity_kg, d.servings,
            d.prepared_time, d.expiry_time,
            d.pickup_address, d.city, d.state, d.pincode,
            d.contact_name, d.contact_phone,
            d.packaging_condition, d.temperature_condition, d.hygiene_checked,
            d.created_at
        FROM donations d
        JOIN users u ON d.donor_id = u.id
        WHERE d.id = %s
    """, (donation_id,))

    d = cur.fetchone()

    if not d:
        return "Donation not found", 404

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    # ================= HEADER =================
    logo = None

    logo_path = os.path.join(
        current_app.root_path,
        'static',
        'images',
        'logo.png'
    )

    # 🔥 CHECK FILE EXISTS FIRST (IMPORTANT)
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=60, height=60)
    else:
        logo = Paragraph("<b>FoodShare</b>", styles['Title'])

    title = Paragraph(
        "<font size=20 color='green'><b>FoodShare</b></font><br/>"
        "<font size=12 color='grey'>Donation Receipt</font>",
        styles['Normal']
    )

    header = Table([[logo, title]], colWidths=[70, 400])
    header.setStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])

    elements.append(header)
    elements.append(Spacer(1, 10))

    # Green Divider
    divider = Table([[""]], colWidths=[500])
    divider.setStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.green),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
    ])
    elements.append(divider)
    elements.append(Spacer(1, 15))

    # ================= RECEIPT INFO =================
    info = Table([
        ["Receipt ID:", d[0]],
        ["Date:", str(d[18])]
    ], colWidths=[120, 250])

    info.setStyle([
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold')
    ])

    elements.append(info)
    elements.append(Spacer(1, 15))

    # ================= TABLE STYLE FUNCTION =================
    def styled_table(data):
        table = Table(data, colWidths=[150, 350])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8)
        ]))
        return table

    # ================= DONOR =================
    elements.append(Paragraph("<font color='darkgreen'><b>Donor Details</b></font>", styles['Heading3']))
    elements.append(styled_table([
        ["Name", d[1]],
        ["Contact", f"{d[13]} ({d[14]})"]
    ]))

    # ================= FOOD =================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<font color='darkgreen'><b>Food Details</b></font>", styles['Heading3']))
    elements.append(styled_table([
        ["Title", d[2]],
        ["Type", d[3]],
        ["Category", d[4]],
        ["Quantity", f"<b>{d[5]} kg</b>"],
        ["Servings", d[6] or "N/A"]
    ]))

    # ================= LOCATION =================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<font color='darkgreen'><b>Pickup Location</b></font>", styles['Heading3']))
    elements.append(styled_table([
        ["Address", f"{d[9]}, {d[10]}, {d[11]} - {d[12]}"]
    ]))

    # ================= TIME =================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<font color='darkgreen'><b>Time Details</b></font>", styles['Heading3']))
    elements.append(styled_table([
        ["Prepared Time", str(d[7])],
        ["Expiry Time", str(d[8])]
    ]))

    # ================= SAFETY =================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<font color='darkgreen'><b>Food Safety & Handling</b></font>", styles['Heading3']))
    elements.append(styled_table([
        ["Packaging", d[15]],
        ["Temperature", d[16]],
        ["Hygiene Checked", "Yes" if d[17] else "No"]
    ]))

    # ================= IMPACT =================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<font color='darkgreen'><b>Impact</b></font>", styles['Heading3']))
    people = int(d[5] * 3)
    elements.append(styled_table([
        ["Estimated People Fed", f"{people}"]
    ]))

    # ================= FOOTER =================
    elements.append(Spacer(1, 20))

    footer_line = Table([[""]], colWidths=[500])
    footer_line.setStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TOPPADDING', (0, 0), (-1, -1), 1)
    ])

    elements.append(footer_line)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        "<i>Thank you for contributing to reduce food waste and support the community.</i>",
        styles['Normal']
    ))

    # ================= BUILD =================
    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"FoodShare_Receipt_{donation_id}.pdf",
        mimetype='application/pdf'
    )
    
@donor_bp.route('/edit-donation/<int:donation_id>', methods=['GET', 'POST'])
def edit_donation(donation_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        cur.execute("""
            UPDATE donations
            SET food_title=%s, quantity_kg=%s, expiry_time=%s
            WHERE id=%s AND donor_id=%s
        """, (
            request.form['food_title'],
            request.form['quantity_kg'],
            request.form['expiry_time'],
            donation_id,
            session['user_id']
        ))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('donor.my_donations'))

    cur.execute("SELECT * FROM donations WHERE id=%s AND donor_id=%s",
                (donation_id, session['user_id']))
    donation = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("donor/edit_donation.html", donation=donation)

from flask import request
from datetime import datetime

from flask import request

from flask import request, redirect, url_for, session, render_template

@donor_bp.route('/impact')
def impact():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('auth.login'))

    donor_id = session['user_id']
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    date_filter = ""
    params = [donor_id]

    if start_date and end_date:
        date_filter = " AND DATE(created_at) BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    cur = mysql.connection.cursor()

    # ---------------- KPIs ----------------
    cur.execute(f"""
        SELECT 
            COUNT(*),
            SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END),
            SUM(quantity_kg)
        FROM donations
        WHERE donor_id=%s {date_filter}
    """, tuple(params))
    total, completed, total_kg = cur.fetchone()
    total_kg = total_kg or 0
    people_fed = int(total_kg * 3)

    # ---------------- STATUS PIE ----------------
    cur.execute(f"""
        SELECT status, COUNT(*)
        FROM donations
        WHERE donor_id=%s {date_filter}
        GROUP BY status
    """, tuple(params))
    status_data = cur.fetchall()

    # ---------------- DAILY ----------------
    cur.execute(f"""
        SELECT DATE(created_at), COUNT(*)
        FROM donations
        WHERE donor_id=%s {date_filter}
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
    """, tuple(params))
    daily_data = cur.fetchall()

    # ---------------- WEEKLY ----------------
    cur.execute(f"""
        SELECT CONCAT(YEAR(created_at), '-W', WEEK(created_at)), COUNT(*)
        FROM donations
        WHERE donor_id=%s {date_filter}
        GROUP BY YEAR(created_at), WEEK(created_at)
        ORDER BY YEAR(created_at), WEEK(created_at)
    """, tuple(params))
    weekly_data = cur.fetchall()

    # ---------------- MONTHLY ----------------
    cur.execute(f"""
        SELECT DATE_FORMAT(created_at, '%%b %%Y'), COUNT(*)
        FROM donations
        WHERE donor_id=%s {date_filter}
        GROUP BY DATE_FORMAT(created_at, '%%Y-%%m')
        ORDER BY MIN(created_at)
    """, tuple(params))
    monthly_data = cur.fetchall()

    # ---------------- TABLE ----------------
    cur.execute(f"""
        SELECT id, food_title, quantity_kg, status, created_at
        FROM donations
        WHERE donor_id=%s {date_filter}
        ORDER BY created_at DESC
    """, tuple(params))
    table_data = cur.fetchall()

    cur.close()

    return render_template(
        'donor/impact.html',
        total=total,
        completed=completed,
        total_kg=total_kg,
        people_fed=people_fed,
        status_data=status_data,
        daily_data=daily_data,
        weekly_data=weekly_data,
        monthly_data=monthly_data,
        table_data=table_data,
        start_date=start_date,
        end_date=end_date
    )

@donor_bp.route('/notifications')
def notifications():
    if 'user_id' not in session or session.get('role') != 'donor':
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()

    # 1. Get notifications FIRST
    cur.execute("""
        SELECT message, type, created_at, is_read
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (session['user_id'],))

    notifications = cur.fetchall()

    # 2. Get unread count SECOND
    cur.execute("""
        SELECT COUNT(*) 
        FROM notifications 
        WHERE user_id=%s AND is_read=0
    """, (session['user_id'],))

    unread_count = cur.fetchone()[0]

    cur.close()

    return render_template(
        'donor/notifications.html',
        notifications=notifications,
        unread_count=unread_count
    )
