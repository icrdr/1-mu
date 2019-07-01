from flask_restplus import Resource, reqparse
from .. import api
from ..model import User
from werkzeug.security import check_password_hash
import jwt, base64
from datetime import datetime, timedelta

from . import SECRET_KEY

n_auth = api.namespace('api/token', description='Authorization Operations')

g_user = reqparse.RequestParser()
g_user.add_argument('Authorization', required=True, location='headers',
                    help="Basic authorization or token.")

@n_auth.route('/')
class AuthApi(Resource):
    @api.expect(g_user)
    def get(self):
        auth_data = g_user.parse_args()['Authorization'].split(" ")[1]
        auth = base64.b64decode(auth_data).decode('utf-8').split(":")
        user = User.query.filter_by(login= auth[0]).first()
        if(user):
            if check_password_hash(user.password,auth[1]):
                token = jwt.encode({'id':user.id, 'exp':datetime.utcnow()+timedelta(minutes=30)}, SECRET_KEY)
                return {'token': token.decode('UTF-8')}, 200
            else:
                return api.abort(400, "wrong password")
        else:
            return api.abort(400, "bad auth")

