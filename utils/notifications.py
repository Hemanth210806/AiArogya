"""
utils/notifications.py — Notification helpers for ArogyaAI
"""
from models import db, Notification
from flask_socketio import emit

def create_notification(user_id=None, doctor_id=None, user_type='patient', message='', n_type='appointment'):
    """Create a database notification and emit a real-time event."""
    notif = Notification(
        user_id=user_id,
        doctor_id=doctor_id,
        user_type=user_type,
        message=message,
        notification_type=n_type
    )
    db.session.add(notif)
    db.session.commit()

    # Emit real-time event via SocketIO
    # The room name will be user_{id} or doctor_{id}
    room = f"{user_type}_{user_id if user_type == 'patient' else doctor_id}"
    emit('new_notification', {
        'message': message,
        'type': n_type,
        'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }, room=room, namespace='/')
    
    return notif
