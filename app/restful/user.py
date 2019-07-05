from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db
from ..model import User, PERMISSIONS
from ..utility import buildUrl
from werkzeug.security import generate_password_hash
from .decorator import permission_required, admin_required

n_user = api.namespace('api/user', description='User Operations')

m_wx_user = api.model('user', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'nickname': fields.String(description="Display name for the user."),
    'sex': fields.String(description="The title for the user."),
    'headimg_url': fields.String(description="The avatar url for the user."),
})

m_user = api.model('user', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'title': fields.String(description="The title for the user."),
    'email': fields.String(description="The email address for the user."),
    'phone': fields.String(description="The phone number for the user."),
    'avatar_url': fields.String(attribute=lambda x: buildUrl(x.avatar_url), description="The avatar url for the user."),
    'reg_date': fields.String(description="Registration date for the user."),
    'role': fields.String(
        attribute=lambda x: str(x.role.name),
        description="The user's role"
    ),
    'followed_count': fields.Integer(
        attribute=lambda x: len(x.followed_users),
        description="The count of user's followed."
    ),
    'follower_count': fields.Integer(
        attribute=lambda x: len(x.follower_users),
        description="The count of user's follower."
    ),
    'wx_user': fields.Nested(m_wx_user),
})

g_user = reqparse.RequestParser()
g_user.add_argument('role_id', location='args', action='split',
                    help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")
g_user.add_argument('include', location='args', action='split',
                    help="Limit result set to specific IDs.")
g_user.add_argument('exclude', location='args', action='split',
                    help="Ensure result set excludes specific IDs.")
g_user.add_argument('order', location='args', default='asc',
                    choices=['asc', 'desc'],
                    help="Order sort attribute ascending or descending.")
g_user.add_argument('orderby', location='args', default='id',
                    choices=['id', 'name', 'reg_date'],
                    help="Sort collection by object attribute.")
g_user.add_argument('page', location='args', type=int, default=1,
                    help="Current page of the collection.")
g_user.add_argument('pre_page', location='args', type=int, default=10,
                    help="Maximum number of items to be returned in result set.")

p_user = reqparse.RequestParser()
p_user.add_argument('login', location='args', required=True,
                    help="Login name for the user.")
p_user.add_argument('password', location='args', required=True,
                    help="Password for the user (never included).")
p_user.add_argument('email', location='args',
                    help="The email address for the user.")
p_user.add_argument('phone', location='args',
                    help="The phone number for the user.")

u_user = reqparse.RequestParser()
u_user.add_argument('name', location='args',
                    help="Display name for the user.")
u_user.add_argument('email', location='args',
                    help="The email address for the user.")
u_user.add_argument('phone', location='args',
                    help="The phone number for the user.")
u_user.add_argument('title', location='args',
                    help="The title for the user.")
u_user.add_argument('avatar_url', location='args',
                    help="The avatar url for the user.")


@n_user.route('')
class UsersApi(Resource):
    @api.marshal_with(m_user, envelope='users')
    @api.expect(g_user)
    @permission_required()
    def get(self):
        args = g_user.parse_args()
        query = User.query
        if args['role_id']:
            query = query.filter(User.role_id.in_(args['role_id']))

        if args['include']:
            if args['exclude']:
                api.abort(400, "include or exclude, not both")
            query = query.filter(User.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(User.id.notin_(args['exclude']))

        if args['orderby'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(User.id.asc())
            else:
                query = query.order_by(User.id.desc())
        elif args['orderby'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(User.name.asc())
            else:
                query = query.order_by(User.name.desc())
        elif args['orderby'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(User.reg_date.asc())
            else:
                query = query.order_by(User.reg_date.desc())

        users_list = query.paginate(
            args['page'], args['pre_page'], error_out=False).items

        if(users_list):
            return users_list, 200
        else:
            api.abort(400, "users doesn't exist")

    @api.marshal_with(m_user)
    @api.expect(p_user)
    def post(self):
        args = p_user.parse_args()
        if not User.query.filter_by(login=args['login']).first():
            hashed_password = generate_password_hash(
                args['password'], method='sha256')
            new_user = User(
                login=args['login'],
                name=args['login'],
                password=hashed_password
            )

            if args['email']:
                if not User.query.filter_by(email=args['email']).first():
                    new_user.email = args['email']
                else:
                    api.abort(400, "email already exist")
            if args['phone']:
                if not User.query.filter_by(phone=args['phone']).first():
                    new_user.phone = args['phone']
                else:
                    api.abort(400, "phone already exist")

            db.session.add(new_user)
            db.session.commit()
            return new_user, 201
        else:
            api.abort(400, "login name already exist")


@n_user.route('/<int:id>')
class UserApi(Resource):
    @api.marshal_with(m_user)
    @permission_required()
    def get(self, id):
        user = User.query.get(id)
        if(user):
            return user, 200
        else:
            api.abort(400, "user doesn't exist")

    @api.marshal_with(m_user)
    @api.expect(u_user)
    @permission_required()
    def put(self, id):
        args = u_user.parse_args()
        user = User.query.get(id)
        if g.current_user.id != id:
            api.abort(400, "you don't have permission")
        if user:
            if args['name']:
                user.name = args['name']
            if args['email']:
                user.email = args['email']
            if args['phone']:
                user.phone = args['phone']
            if args['title']:
                user.title = args['title']
            if args['avatar_url']:
                user.avatar_url = args['avatar_url']
            db.session.commit()
            return user, 200
        else:
            api.abort(400, "login name already exist")

    @admin_required
    def delete(self, id):
        user = User.query.get(id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return {'message': 's!'}, 200
        else:
            api.abort(400, "user doesn't exist")
