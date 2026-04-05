from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from app.extensions import socketio


@socketio.on('connect')
def handle_connect(auth):
    try:
        if auth and 'token' in auth:
            token_data = decode_token(auth['token'])
            user_id = token_data['sub']
            join_room(f'user_{user_id}')
            emit('connected', {'status': 'success', 'user_id': user_id})
        else:
            return False
    except Exception:
        return False


@socketio.on('disconnect')
def handle_disconnect():
    pass


@socketio.on('join_alerts')
def handle_join_alerts(data):
    try:
        if 'token' in data:
            token_data = decode_token(data['token'])
            user_id = token_data['sub']
            join_room(f'alerts_user_{user_id}')
            emit('joined_alerts', {'status': 'success'})
    except Exception:
        emit('error', {'message': 'Invalid token'})


@socketio.on('leave_alerts')
def handle_leave_alerts(data):
    try:
        if 'token' in data:
            token_data = decode_token(data['token'])
            user_id = token_data['sub']
            leave_room(f'alerts_user_{user_id}')
            emit('left_alerts', {'status': 'success'})
    except Exception:
        pass
