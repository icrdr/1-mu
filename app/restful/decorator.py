from flask_restplus import reqparse
from functools import wraps
from flask import g
from .. import api, app
from ..model import User
from werkzeug.security import check_password_hash
import jwt, base64

from . import PERMISSIONS, SECRET_KEY

g_user = reqparse.RequestParser()
g_user.add_argument('Authorization', required=True, location='headers',
                    help="Basic authorization or token.")

def permission_required(permission=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = g_user.parse_args()['Authorization'].split(" ")[1]
            data = jwt.decode(token, SECRET_KEY)
            user = User.query.get(data['id'])
            if user:
                g.current_user = User.query.get(data['id'])
                g.token_used = True
            else:
                return api.abort(400, "bad token")
            
            if permission:
                if not g.current_user.can(permission):
                    api.abort(400, "Insufficient permissions")
    
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return permission_required(PERMISSIONS['ADMIN'])(f)