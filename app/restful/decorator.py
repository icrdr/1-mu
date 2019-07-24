from flask_restplus import reqparse
from functools import wraps
from flask import g, request
from .. import api, app
from ..model import User
from werkzeug.security import check_password_hash
import jwt, base64
PERMISSIONS = app.config['PERMISSIONS']
g_user = reqparse.RequestParser()
# g_user.add_argument('Authorization', required=True, location='headers',
#                     help="Basic authorization or token.")
g_user.add_argument('token',location='cookies',
                    help="Basic authorization or token.")

def permission_required(permission=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # token = g_user.parse_args()['Authorization'].split(" ")[1]
            args = g_user.parse_args()
            if not args['token']:
                return api.abort(401, "No token was given.")

            try:
                data = jwt.decode(args['token'], app.config['SECRET_KEY'])
            except Exception as e:
                print(e)
                return api.abort(401, "Bad token.")

            user = User.query.get(data['id'])
            if user:
                g.current_user = User.query.get(data['id'])
                g.token_used = True
            else:
                return api.abort(401, "User is not exist")
            
            if permission:
                if not g.current_user.can(permission):
                    api.abort(403, "More privileges required.")
    
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return permission_required(PERMISSIONS['ADMIN'])(f)