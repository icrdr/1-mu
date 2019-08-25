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
        attribute=lambda x: len(list(filter(is_unread, x.project_notices_as_receiver)))
    ),
    'followed_count': fields.Integer(
        attribute=lambda x: len(x.followed_users)
    ),
    'follower_count': fields.Integer(
        attribute=lambda x: len(x.follower_users)
    ),
    'wx_user': fields.Nested(m_wx_user),
})

m_auth = api.model('users', {
    'user': fields.Nested(M_USER),
    'token': fields.String,
})

g_auth = reqparse.RequestParser()
g_auth.add_argument('Authorization', required=True, location='headers')

@n_auth.route('')
class AuthApi(Resource):
    @api.expect(g_auth)
    def get(self):
        args = g_auth.parse_args()
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
                return marshal(output, m_auth), 200
            else:
                return api.abort(400, "Wrong password.")
        else:
            return api.abort(400, "User isnot exist.")


n_me = api.namespace('api/me', description='Me')
g_user = reqparse.RequestParser()
g_user.add_argument('token', location='cookies')

@n_me.route('')
class MeApi(Resource):
    @api.marshal_with(M_USER)
    @api.expect(g_user)
    def get(self):
        args = g_user.parse_args()
        try:
            print(args['token'])
            data = jwt.decode(args['token'], app.config['SECRET_KEY'])
            print(data)
        except Exception as e:
            print(e)
            return api.abort(401, "Bad token.")

        user = User.query.get(data['id'])
        if user:
            output = {
                'user': user,
            }
            return user, 200
        else:
            return api.abort(401, "User is not exist")