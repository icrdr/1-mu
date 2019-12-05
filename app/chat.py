from flask_socketio import emit, send, join_room, leave_room, rooms, disconnect
from app import api, app
from .model import User
from app import socketio
from flask import g, request
import jwt
from functools import wraps


def authenticated_only(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = request.cookies['token']
        data = jwt.decode(token, app.config['SECRET_KEY'])
        user = User.query.get(data['id'])
        if not user:
            disconnect()
        else:
            g.current_user = user
            return f(*args, **kwargs)
    return wrapped


@socketio.on('message')
@authenticated_only
def handle_message(res):
    print('received message from {}: {}'.format(
        g.current_user.name, res['content']))
    send({'name': g.current_user.name,
          'content': res['content']}, room=res['room'])


@socketio.on('join')
@authenticated_only
def handle_join_room(res):
    if not res['room'] in rooms():
        join_room(res['room'])
        print('{} join room: {}'.format(g.current_user.name, res['room']))
        send({'name': '📢系统',
              'content': '%s加入了讨论' % g.current_user.name}, include_self=False, room=res['room'])


@socketio.on('leave')
@authenticated_only
def handle_leave_room(res):
    leave_room(res['room'])
    print('{} leave room: {}'.format(g.current_user.name, res['room']))
    send({'name': '📢系统',
          'content': '%s离开了讨论' % g.current_user.name}, include_self=False, room=res['room'])