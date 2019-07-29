from flask_restplus import Resource, reqparse, fields, marshal
from flask import g, request
from .. import api, db,app
from ..model import User, Group
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

M_GROUP_MEMBER = api.model('group_member', {
    'id': fields.Integer(),
    'name': fields.String(),
    'avatar_url': fields.String(attribute=getAvatar),
})

M_GROUP = api.model('group', {
    'id': fields.Integer(),
    'name': fields.String(),
    'description': fields.String(),
    'admins': fields.List(fields.Nested(M_GROUP_MEMBER)),
    'users': fields.List(fields.Nested(M_GROUP_MEMBER)),
})
M_GROUP_MIN = api.model('group_min)', {
    'id': fields.Integer(),
    'name': fields.String(),
})
M_USER = api.model('user', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'title': fields.String(description="The title for the user."),
    'sex': fields.String(description="The phone number for the user."),
    'email': fields.String(description="The email address for the user."),
    'phone': fields.String(description="The phone number for the user."),
    'avatar_url': fields.String(attribute=getAvatar),
    'groups': fields.Nested(M_GROUP_MIN),
    'groups_as_admin': fields.Nested(M_GROUP_MIN),
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

M_USERS = api.model('users', {
    'users': fields.List(fields.Nested(M_USER)),
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
        
        output = {
            'users':users,
            'total':total
        }
        return marshal(output, M_USERS), 200

    @api.marshal_with(M_USER)
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

    @api.marshal_with(M_USER, envelope='users')
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

@n_user.route('/<int:user_id>')
class UserApi(Resource):
    @api.marshal_with(M_USER)
    def get(self, user_id):
        user = User.query.get(user_id)
        if(user):
            return user, 200
        else:
            api.abort(400, "user doesn't exist")

#     @admin_required
#     def delete(self, id):
#         user = User.query.get(id)
#         if user:
#             db.session.delete(user)
#             db.session.commit()
#             return {'message': 's!'}, 200
#         else:
#             api.abort(400, "user doesn't exist")

N_GROUP = api.namespace('api/groups', description='Group Operations')


M_GROUPS = api.model('groups', {
    'groups': fields.List(fields.Nested(M_GROUP)),
    'total': fields.Integer(description="Unique identifier for the user."),
})
G_GROUP = reqparse.RequestParser()\
    .add_argument('include', location='args', action='split')\
    .add_argument('exclude', location='args', action='split')\
    .add_argument('order', location='args', default='asc',choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id',choices=['id', 'name', 'reg_date'])\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)

@N_GROUP.route('')
class GroupsApi(Resource):
    @api.expect(G_GROUP)
    # @permission_required()
    def get(self):
        args = G_GROUP.parse_args()
        query = Group.query

        if args['include']:
            if args['exclude']:
                api.abort(400, "include or exclude, not both")
            query = query.filter(Group.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(Group.id.notin_(args['exclude']))

        if args['order_by'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(Group.id.asc())
            else:
                query = query.order_by(Group.id.desc())
        elif args['order_by'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(Group.name.asc())
            else:
                query = query.order_by(Group.name.desc())
        elif args['order_by'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(Group.reg_date.asc())
            else:
                query = query.order_by(Group.reg_date.desc())

        record_query = query.paginate(
            args['page'], args['pre_page'], error_out=False)
        groups = record_query.items
        total = record_query.total
        
        output = {
            'groups':groups,
            'total':total
        }
        return marshal(output, M_GROUPS), 200

@N_GROUP.route('/<int:group_id>/add/<int:user_id>')
class GroupAddApi(Resource):
    @api.marshal_with(M_GROUP)
    @permission_required()
    def put(self, group_id, user_id):
        group = groupCheck(group_id)
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if not g.current_user in group.admins:
                api.abort(
                    403, "Only the group's admin can add member(Administrator privileges required).")

        user = User.query.get(user_id)

        if not user:
            api.abort(401, "User is not exist.")
        elif user in group.users:
            api.abort(401, "User is already member.")
        group.users.append(user)

        db.session.commit()
        return group, 200

@N_GROUP.route('/<int:group_id>/remove/<int:user_id>')
class GroupAddApi(Resource):
    @api.marshal_with(M_GROUP)
    @permission_required()
    def put(self, group_id, user_id):
        group = groupCheck(group_id)
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if not g.current_user in group.admins:
                api.abort(
                    403, "Only the group's admin can remove member(Administrator privileges required).")

        user = User.query.get(user_id)

        if not user:
            api.abort(401, "User is not exist.")
        elif not user in group.users:
            api.abort(401, "User is not member.")

        group.users.remove(user)

        db.session.commit()
        return group, 200

def groupCheck(group_id):
    group = Group.query.get(group_id)
    if not group:
        api.abort(400, "group is not exist.")
    else:
        return group