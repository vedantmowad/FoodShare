from db import get_connection

def add_notification(user_id, message, ntype="info"):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO notifications (user_id, message, type)
        VALUES (%s, %s, %s)
    """, (user_id, message, ntype))

    conn.commit()
    cur.close()
    conn.close()
