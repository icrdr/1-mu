from flask_restplus import Resource, reqparse, fields, marshal
from flask import g, request
from .. import api, db,app
from ..model import User
from ..utility import buildUrl, getAvatar
from werkzeug.security import generate_password_hash
from .decorator import permission_required, admin_required
PERMISSIONS = app.config['PERMISSIONS']
n_user = api.namespace('api/users', description='User Operations')

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
    'sex': fields.String(description="The phone number for the user."),
    'email': fields.String(description="The email address for the user."),
    'phone': fields.String(description="The phone number for the user."),
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x), description="The avatar url for the user."),
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

m_users = api.model('users', {
    'users': fields.List(fields.Nested(m_user)),
    'total': fields.Integer(description="Unique identifier for the user."),
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
g_user.add_argument('order_by', location='args', default='id',
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
u_user.add_argument('use_id', location='args', action='split', required=True,
                       help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")
u_user.add_argument('name', location='args',
                    help="Display name for the user.")
u_user.add_argument('email', location='args',
                    help="The email address for the user.")
u_user.add_argument('phone', location='args',
                    help="The phone number for the user.")
u_user.add_argument('title', location='args',
                    help="The title for the user.")

d_user = reqparse.RequestParser()
d_user.add_argument('user_id', location='args', action='split', required=True,
                       help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")

@n_user.route('')
class UsersApi(Resource):
    @api.expect(g_user)
    # @permission_required()
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

        if args['order_by'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(User.id.asc())
            else:
                query = query.order_by(User.id.desc())
        elif args['order_by'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(User.name.asc())
            else:
                query = query.order_by(User.name.desc())
        elif args['order_by'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(User.reg_date.asc())
            else:
                query = query.order_by(User.reg_date.desc())

        record_query = query.paginate(
            args['page'], args['pre_page'], error_out=False)
        users = record_query.items
        total = record_query.total
        
        if(users):
            output = {
                'users':users,
                'total':total
            }
            return marshal(output, m_users), 200
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

    @api.marshal_with(m_user, envelope='users')
    @api.expect(u_user)
    def put(self):
        args = u_user.parse_args()
        users = User.query.filter(
            User.id.in_(args['user_id'])).all()
        if users:
            for user in users:
                try:
                    if args['name']:
                        user.name = args['name']
                    if args['email']:
                        user.email = args['email']
                    if args['phone']:
                        user.phone = args['phone']
                    if args['title']:
                        user.title = args['title']
                    db.session.commit()
                except Exception as e:
                    print(e)
                    api.abort(400, e)         
            return users, 200
        else:
            api.abort(400, "login name already exist")

    def delete(self):
        args = d_user.parse_args()
        users = User.query.filter(
            User.id.in_(args['user_id'])).all()
        if users:
            for user in users:
                if user.wx_user:
                    db.session.delete(user.wx_user)
                db.session.delete(user)
            db.session.commit()
            return {'message': 'ok!'}, 200
        else:
            api.abort(400, "user doesn't exist")

# @n_user.route('/<int:id>')
# class UserApi(Resource):
#     @api.marshal_with(m_user)
#     @permission_required()
#     def get(self, id):
#         user = User.query.get(id)
#         if(user):
#             return user, 200
#         else:
#             api.abort(400, "user doesn't exist")

#     

#     @admin_required
#     def delete(self, id):
#         user = User.query.get(id)
#         if user:
#             db.session.delete(user)
#             db.session.commit()
#             return {'message': 's!'}, 200
#         else:
#             api.abort(400, "user doesn't exist")
