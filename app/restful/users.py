from flask_restplus import Resource, reqparse, fields, marshal
from flask import g, request
from .. import api, db, app
from ..model import User, Group, ProjectNotice
from ..utility import buildUrl, getAvatar,getStageIndex,getPhaseIndex
from werkzeug.security import generate_password_hash
from .decorator import permission_required, admin_required
PERMISSIONS = app.config['PERMISSIONS']
N_USER = api.namespace('api/users', description='User Operations')

m_wx_user = api.model('user', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'nickname': fields.String(description="Display name for the user."),
    'sex': fields.String(description="The title for the user."),
    'headimg_url': fields.String(description="The avatar url for the user."),
})

M_MIN_USER = api.model('group_member', {
    'id': fields.Integer(),
    'name': fields.String(),
    'avatar_url': fields.String(attribute=getAvatar),
})

M_GROUP = api.model('group', {
    'id': fields.Integer(),
    'name': fields.String(),
    'description': fields.String(),
    'admins': fields.List(fields.Nested(M_MIN_USER)),
    'users': fields.List(fields.Nested(M_MIN_USER)),
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
p_user.add_argument('email', location='args', default='',
                    help="The email address for the user.")
p_user.add_argument('phone', location='args', default='',
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


@N_USER.route('')
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

        total = len(query.all())
        users = query.limit(args['pre_page']).offset((args['page']-1)*args['pre_page']).all()

        output = {
            'users': users,
            'total': total
        }
        return marshal(output, M_USERS), 200

    @api.marshal_with(M_USER)
    @api.expect(p_user)
    def post(self):
        args = p_user.parse_args()

        if User.query.filter_by(login=args['login']).first():
            api.abort(400, "login name already exist")

        if args['email'] != None:
            if User.query.filter_by(email=args['email']).first():
                api.abort(400, "email already exist")

        if args['phone'] != None:
            if User.query.filter_by(phone=args['phone']).first():
                api.abort(400, "phone already exist")
        try:
            new_user = User.create_user(
                login=args['login'],
                password=args['password'],
                email = args['email'],
                phone = args['phone']
            )
        except Exception as e:
            print(e)
            api.abort(400, "Failed of creating user.")

        return new_user, 201
        
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

@N_USER.route('/<int:user_id>')
class UserApi(Resource):
    @api.marshal_with(M_USER)
    def get(self, user_id):
        user = userCheck(user_id)
        return user, 200

    @admin_required
    def delete(self, user_id):
        user = userCheck(user_id)
        try:
            user.delete()
            return {'message': 'ok!'}, 200
        except Exception as e:
            print(e)
            api.abort(400, "delete fail!")

M_MIN_PROJECT = api.model('project', {
    'id': fields.Integer(),
    'title': fields.String(),
})

M_MIN_PHASE = api.model('phase', {
    'id': fields.Integer(),
    'name': fields.String(),
})

M_MIN_STAGE = api.model('stage', {
    'id': fields.Integer(),
    'name': fields.String(),
})

M_PROJECT_NOTICE = api.model('project_notice', {
    'id': fields.Integer(),
    'from_user': fields.Nested(M_MIN_USER),
    'notice_type': fields.String(),
    'send_date': fields.String,
    'parent_project': fields.Nested(M_MIN_PROJECT),
    'parent_phase': fields.Nested(M_MIN_PHASE),
    'parent_stage': fields.Nested(M_MIN_STAGE),
    'stage_index': fields.Integer(attribute=lambda x: getStageIndex(x.parent_stage)),
    'phase_index': fields.Integer(attribute=lambda x: getPhaseIndex(x.parent_phase)),
    'cover_url': fields.String(attribute=lambda x: buildUrl(x.cover_url)),
    'content': fields.String(),
    'read': fields.Integer()
})
            

M_PROJECT_NOTICES = api.model('project_notices', {
    'project_notices': fields.List(fields.Nested(M_PROJECT_NOTICE)),
    'total': fields.Integer,
    'unread': fields.Integer,
})

N_PROJECT_NOTICE = api.namespace('api/project_notices', description='User Operations')

G_PROJECT_NOTICE = reqparse.RequestParser()\
    .add_argument('user_id', location='args', type=int, required=True )\
    .add_argument('only_unread', location='args', type=int, default=1)\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)\

U_PROJECT_NOTICE = reqparse.RequestParser()\
    .add_argument('user_id', type=int, required=True )\

@N_PROJECT_NOTICE.route('')
class UserProjectNotiecsApi(Resource):
    def get(self):
        args = G_PROJECT_NOTICE.parse_args()
        user = userCheck(args['user_id'])
        query = ProjectNotice.query.filter_by(to_user_id=args['user_id']).filter_by(read=False)
        total = query.all()
        unread = query.filter_by(read=False).all()

        if(args['only_unread']):
            query = query.filter_by(read=False)

        notices = query.order_by(ProjectNotice.id.desc()).limit(args['pre_page']).offset((args['page']-1)*args['pre_page']).all()

        output = {
            'project_notices': notices,
            'total': len(total),
            'unread':len(unread)
        }
        return marshal(output, M_PROJECT_NOTICES, skip_none=True), 200
    
    def put(self):
        args = U_PROJECT_NOTICE.parse_args()
        user = userCheck(args['user_id'])
        query = ProjectNotice.query.filter_by(to_user_id=args['user_id']).filter_by(read=False).order_by(ProjectNotice.id.desc())

        notices = query.all()
        for notice in query.all():
            notice.set_read()

        return {'message': 'ok'}, 200

@N_PROJECT_NOTICE.route('/<int:notice_id>')
class UserProjectNotiecApi(Resource): 
    def put(self, notice_id):
        notice = projectNoticeCheck(notice_id)
        notice.set_read()

        return {'message': 'ok'}, 200

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

P_GROUP = reqparse.RequestParser()\
    .add_argument('name', required=True)\
    .add_argument('description')\
    .add_argument('admin_id', action='append')\
    .add_argument('user_id', action='append')

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

        total = len(query.all())
        groups = query.limit(args['pre_page']).offset((args['page']-1)*args['pre_page']).all()
        
        output = {
            'groups':groups,
            'total':total
        }
        return marshal(output, M_GROUPS), 200

    @api.marshal_with(M_GROUP)
    @permission_required()
    def post(self):
        args = P_GROUP.parse_args()

        for _id in args['admin_id']:
            if not User.query.get(_id):
                api.abort(401, "Admin is not exist.")

        for _id in args['user_id']:
            if not User.query.get(_id):
                api.abort(401, "User is not exist.")

        try:
            new_group = Group.create_group(
                name=args['name'],
                description=args['description'],
                admin_id=args['admin_id'],
                user_id=args['user_id'],
            )
            return new_group, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_GROUP.route('/<int:group_id>/add/<int:user_id>')
class GroupAddUserApi(Resource):
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
class GroupRemoveUserApi(Resource):
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

@N_GROUP.route('/<int:group_id>')
class GroupRemoveApi(Resource):
    @permission_required()
    def delete(self, group_id):
        group = groupCheck(group_id)
        group.delete()
        return {'message': 'ok'}, 204

def groupCheck(group_id):
    group = Group.query.get(group_id)
    if not group:
        api.abort(400, "group is not exist.")
    else:
        return group

def userCheck(user_id):
    user = User.query.get(user_id)
    if not user:
        api.abort(400, "user is not exist.")
    else:
        return user

def projectNoticeCheck(notice_id):
    notice = ProjectNotice.query.get(notice_id)
    if not notice:
        api.abort(400, "notice is not exist.")
    else:
        return notice
