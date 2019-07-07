from flask_restplus import Resource, reqparse
from .. import api, app, db
from ..model import User, WxUser
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
import base64
import requests
import shortuuid
from datetime import datetime, timedelta

n_auth = api.namespace('api/auth', description='Authorization Operations')

g_user = reqparse.RequestParser()
g_user.add_argument('Authorization', required=True, location='headers')

@n_auth.route('')
class AuthApi(Resource):
    @api.expect(g_user)
    def get(self):
        args = g_user.parse_args()
        auth_data = args['Authorization'].split(" ")[1]
        auth = base64.b64decode(auth_data).decode('utf-8').split(":")
        user = User.query.filter_by(login=auth[0]).first()
        if(user):
            if check_password_hash(user.password, auth[1]):
                token = jwt.encode({'id': user.id, 'exp': datetime.utcnow(
                )+timedelta(hours = 24)}, app.config['SECRET_KEY'])
                return {'token': token.decode('UTF-8')}, 200
            else:
                return api.abort(400, "wrong password")
        else:
            return api.abort(400, "user not exist")
