from flask_restplus import Resource, reqparse, fields
from flask import request
from .. import api, db, app
from ..model import User
from werkzeug.security import check_password_hash
import uuid, jwt, base64
from datetime import datetime, timedelta
from functools import wraps

SECRET_KEY = app.config['SECRET_KEY']

n_auth = api.namespace('api/auth', description='TODO operations')

g_user = reqparse.RequestParser()
g_user.add_argument('Authorization', required=True, location='headers')

@n_auth.route('/')
class Authx(Resource):
    def get(self):
        auth_data = g_user.parse_args()['Authorization'].split(" ")[1]
        auth = base64.b64decode(auth_data).decode('utf-8').split(":")
        print(auth)
        user = User.query.filter_by(username= auth[0]).first()
        if(user):
            if check_password_hash(user.password,auth[1]):
                token = jwt.encode({'public_id':user.public_id, 'exp':datetime.utcnow()+timedelta(minutes=30)}, SECRET_KEY)
            return {'token': token.decode('UTF-8')}
        else:
            return {"error": "f!"}

def requires_auth(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        parse = reqparse.RequestParser()
        parse.add_argument('Authorization', required=True, location='headers')
        prm = parse.parse_args()
        token = prm['Authorization'].split(" ")[1]
        # print(token)
        try:
            data = jwt.decode(token,SECRET_KEY)
            current_user = User.query.filter_by(public_id=data['public_id']).first()
        except:
            return api.abort(404, "bad token")
        return f(*args,current_user,**kwargs)
    return decorated