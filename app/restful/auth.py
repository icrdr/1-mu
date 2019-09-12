from flask_restplus import Resource, reqparse, marshal,fields
from .. import api, app, db
from ..model import User, WxUser
from ..utility import buildUrl, getAvatar
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
import base64
import requests
import shortuuid
from datetime import datetime, timedelta

n_auth = api.namespace('api/auth', description='Authorization Operations')

m_wx_user = api.model('user', {
    'id': fields.Integer,
    'nickname': fields.String,
    'sex': fields.String,
    'headimg_url': fields.String,
})

M_GROUP_MIN = api.model('group_min)', {
    'id': fields.Integer(),
    'name': fields.String(),
})

def is_unread(notice):
    return notice.read == False

M_USER = api.model('user', {
    'id': fields.Integer,
    'name': fields.String,
    'title': fields.String,
    'sex': fields.String,
    'email': fields.String,
    'phone': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x)),
    'reg_date': fields.String,
    'groups': fields.Nested(M_GROUP_MIN),
    'groups_as_admin': fields.Nested(M_GROUP_MIN),
    'role': fields.String(
        attribute=lambda x: str(x.role.name)
    ),
    'unread_count': fields.Integer(
        attribute=lambda x: len(list(filter(is_unread, x.project_notices)))
    ),
    'followed_count': fields.Integer(
        attribute=lambda x: len(x.followed_users)
    ),
    'follower_count': fields.Integer(
        attribute=lambda x: len(x.follower_users)
    ),
    'wx_user': fields.Nested(m_wx_user),
})

M_AUTH = api.model('user_auth', {
    'user': fields.Nested(M_USER),
    'token': fields.String,
})

G_AUTH = reqparse.RequestParser()\
    .add_argument('Authorization', required=True, location='headers')

@n_auth.route('')
class AuthApi(Resource):
    @api.expect(G_AUTH)
    def get(self):
        args = G_AUTH.parse_args()
        auth_data = args['Authorization'].split(" ")[1]
        auth = base64.b64decode(auth_data).decode('utf-8').split(":")
        user = User.query.filter_by(login=auth[0]).first()
        if user:
            if check_password_hash(user.password, auth[1]):
                token = jwt.encode({'id': user.id, 'exp': datetime.utcnow(
                )+timedelta(days=24)}, app.config['SECRET_KEY'])
                output = {
                    'user': user,
                    'token': token.decode('UTF-8')
                }
                return marshal(output, M_AUTH), 200
            else:
                return api.abort(400, "Wrong password.")
        else:
            return api.abort(400, "User isnot exist.")

N_ME = api.namespace('api/me', description='Me')
G_USER = reqparse.RequestParser()\
    .add_argument('token', location='cookies')

@N_ME.route('')
class MeApi(Resource):
    @api.marshal_with(M_USER)
    @api.expect(G_USER)
    def get(self):
        args = G_USER.parse_args()
        try:
            data = jwt.decode(args['token'], app.config['SECRET_KEY'])
        except Exception as e:
            print(e)
            return api.abort(401, "Bad token.")

        user = User.query.get(data['id'])
        if user:
            print("%s is log in."%user.name)
            return user, 200
        else:
            return api.abort(401, "User is not exist")