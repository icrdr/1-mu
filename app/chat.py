from flask_socketio import emit
from app import socketio

@socketio.on('send')
def handle_message2(msg):
    print('received message: ' + msg)
    emit('send', msg, broadcast=True)