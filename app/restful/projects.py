"""
Project Api
"""
from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from sqlalchemy import or_
from .. import api, app, db
from ..model import Stage, Phase, User, File, Project, Tag, Group
from ..utility import buildUrl, getAvatar
from .decorator import permission_required, admin_required

PERMISSIONS = app.config['PERMISSIONS']

N_PROJECT = api.namespace('api/projects', description='projects operations')

M_PREVIEW = api.model('preview', {
    'url': fields.String(attribute=lambda x: buildUrl(x.url)),
})

M_FILE = api.model('file', {
    'id': fields.Integer,
    'name': fields.String,
    'url': fields.String(attribute=lambda x: buildUrl(x.url)),
    'format': fields.String,
    'previews': fields.List(fields.Nested(M_PREVIEW)),
})

M_CREATOR = api.model('creator', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=getAvatar),
})

M_UPLOADER = api.model('uploader', {
    'id': fields.Integer,
    'name': fields.String,
})

M_CLIENT = api.model('client', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=getAvatar),
})

M_TAG = api.model('tag', {
    'id': fields.Integer,
    'name': fields.String,
})

M_PHASE = api.model('phase', {
    'id': fields.Integer,
    'days_need': fields.Integer,
    'upload_date': fields.String,
    'feedback_date': fields.String,
    'creator_upload': fields.String,
    'creator': fields.Nested(M_UPLOADER),
    'client_feedback': fields.String,
    'upload_files': fields.List(fields.Nested(M_FILE))
})

M_STAGE = api.model('stage', {
    'id': fields.Integer,
    'name': fields.String,
    'start_date': fields.String,
    'phases': fields.List(fields.Nested(M_PHASE))
})
M_GROUP = api.model('group', {
    'id': fields.Integer,
    'admins': fields.List(fields.Nested(M_CREATOR)),
    'users': fields.List(fields.Nested(M_CREATOR))
})
M_PROJECT = api.model('project', {
    'id': fields.Integer,
    'title': fields.String,
    'design': fields.String,
    'status': fields.String,
    'creator_group': fields.Nested(M_GROUP),
    'client': fields.Nested(M_CLIENT),
    'public_date': fields.String,
    'start_date': fields.String,
    'finish_date': fields.String,
    'current_stage_index': fields.Integer,
    'stages': fields.List(fields.Nested(M_STAGE)),
    'tags': fields.List(fields.Nested(M_TAG)),
})
M_PROJECTS = api.model('projects', {
    'projects': fields.List(fields.Nested(M_PROJECT)),
    'total': fields.Integer,
})

GET_PROJECT = reqparse.RequestParser()\
    .add_argument('creator_id', location='args', action='split')\
    .add_argument('client_id', location='args', action='split')\
    .add_argument('title', location='args', action='split')\
    .add_argument('search', location='args')\
    .add_argument('status', location='args', action='split')\
    .add_argument('include', location='args', action='split')\
    .add_argument('exclude', location='args', action='split')\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)\
    .add_argument('order', location='args', default='asc', choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id', choices=['id', 'title', 'start_date'])

POST_PROJECT = reqparse.RequestParser()\
    .add_argument('title', required=True)\
    .add_argument('group_id', type=int)\
    .add_argument('creators', type=int, action='append')\
    .add_argument('client_id', type=int, required=True)\
    .add_argument('design', required=True)\
    .add_argument('stages', type=list, location='json', required=True)\
    .add_argument('confirm', type=int, default=0)\
    .add_argument('tags', action='append')\
    .add_argument('files', type=int, action='append')


@N_PROJECT.route('')
class PorjectsApi(Resource):
    @api.expect(GET_PROJECT)
    def get(self):
        args = GET_PROJECT.parse_args()
        query = Project.query
        if args['creator_id']:
            query = query.join(Project.creator_group).join(Group.users).filter(
                User.id.in_(args['creator_id']))
        if args['client_id']:
            query = query.filter(Project.client_user_id.in_(args['client_id']))
        if args['title']:
            query = query.filter(Project.title.in_(args['title']))

        if args['status']:
            query = query.filter(Project.status.in_(args['status']))

        if args['search']:
            query = query.join(Project.tags).filter(
                or_(Project.title.contains(args['search']), Tag.name.contains(args['search'])))

        if args['include']:
            if args['exclude']:
                api.abort(401, "include or exclude, not both")
            query = query.filter(Project.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(Project.id.notin_(args['exclude']))

        if args['order_by'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(Project.id.asc())
            else:
                query = query.order_by(Project.id.desc())
        elif args['order_by'] == 'title':
            if args['order'] == 'asc':
                query = query.order_by(Project.title.asc())
            else:
                query = query.order_by(Project.title.desc())
        elif args['order_by'] == 'start_date':
            if args['order'] == 'asc':
                query = query.order_by(Project.start_date.asc())
            else:
                query = query.order_by(Project.start_date.desc())

        record_query = query.paginate(
            args['page'], args['pre_page'], error_out=False)
        projects = record_query.items
        total = record_query.total

        output = {
            'projects': projects,
            'total': total
        }
        return marshal(output, M_PROJECTS, skip_none=True), 200

    @api.marshal_with(M_PROJECT)
    @api.expect(POST_PROJECT)
    @permission_required()
    def post(self):
        args = POST_PROJECT.parse_args()
        # permission checking
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if (not g.current_user.id in args['creators']):
                return api.abort(403, "Poster must be one of the creators(Administrator privileges required).")
        if not User.query.get(args['client_id']):
            return api.abort(401, "Client is not exist.")
        if not Group.query.get(args['group_id']):
            return api.abort(401, "Group is not exist.")
        try:
            new_project = Project.create_project(
                title=args['title'],
                client_id=args['client_id'],
                creators=args['creators'],
                group_id=args['group_id'],
                design=args['design'],
                stages=args['stages'],
                tags=args['tags'],
                files=args['files'],
                confirm=args['confirm'],
            )
            return new_project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


UPDATE_PROJECT = reqparse.RequestParser()\
    .add_argument('title')\
    .add_argument('group_id', type=int)\
    .add_argument('client_id', type=int, )\
    .add_argument('design')\
    .add_argument('files', type=int, action='append')



@N_PROJECT.route('/<int:project_id>')
class PorjectApi(Resource):
    @api.marshal_with(M_PROJECT)
    def get(self, project_id):
        project = projectCheck(project_id)
        return project, 200

    @api.marshal_with(M_PROJECT)
    @api.expect(UPDATE_PROJECT)
    @permission_required()
    def put(self, project_id):
        args = UPDATE_PROJECT.parse_args()
        project = projectCheck(project_id)
        if args['client_id']:
            if not User.query.get(args['client_id']):
                return api.abort(401, "Client is not exist.")
        if args['group_id']:
            if not Group.query.get(args['group_id']):
                return api.abort(401, "Group is not exist.")
        if not g.current_user.can(PERMISSIONS['EDIT']):
            if (not g.current_user in project.creator_group.users) or (project.status != 'await'):
                api.abort(
                    403, "Administrator privileges required for request update action.")

        try:
            if args['client_id'] != None:
                project.client_user_id = args['client_id']
            if args['title'] != None:
                project.title = args['title']
            if args['design'] != None:
                project.design = args['design']
            if args['group_id']:
                project.creator_group_id = args['group_id']
            
            if args['files']:
                project.files = []
                for file_id in args['files']:
                    file = File.query.get(file_id)
                    project.files.append(file)

            db.session.commit()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))

    @admin_required
    def delete(self, project_id):
        project = projectCheck(project_id)
        project.delete()
        return {'message': 'ok'}, 204


@N_PROJECT.route('/<int:project_id>/start')
class PorjectStartApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = projectCheck(project_id)
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if g.current_user.id != project.client_user_id:
                api.abort(
                    403, "Only the project's client can start(Administrator privileges required).")
        if project.status != 'await':
            api.abort(401, "Project is already started.")

        try:
            project.start()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


UPLOAD_PROJECT = reqparse.RequestParser()\
    .add_argument('upload', required=True)\
    .add_argument('upload_files', type=list, location='json', required=True)\
    .add_argument('confirm', type=int, default=0)


@N_PROJECT.route('/<int:project_id>/upload')
class PorjectUploadApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        args = UPLOAD_PROJECT.parse_args()
        project = Project.query.get(project_id)
        for upload_file in args['upload_files']:
            if not File.query.get(upload_file['id']):
                api.abort(401, "File is not exist.")
        if project.status != 'modify' and project.status != 'progress':
            api.abort(
                401, "Creator can upload only during 'modify' or 'progress'.")
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if not g.current_user in project.creator_group.users:
                api.abort(
                    403, "Only the project's creator can upload(Administrator privileges required).")
        try:
            project.upload(
                g.current_user.id,
                args['upload'],
                args['upload_files'],
                args['confirm']
            )
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


MODIFY_PROJECT = reqparse.RequestParser()\
    .add_argument('feedback', required=True)\
    .add_argument('confirm', type=int, default=0)


@N_PROJECT.route('/<int:project_id>/modify')
class PorjectModifyApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        args = MODIFY_PROJECT.parse_args()
        project = Project.query.get(project_id)
        if project.status != 'pending':
            api.abort(
                401, "Project can be set to 'modify' only after creator's upload.")
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if g.current_user.id != project.client_user_id:
                api.abort(
                    403, "Only the project's client can feedback(Administrator privileges required).")

        try:
            project.modify(g.current_user.id,
                           args['feedback'], args['confirm'])
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_PROJECT.route('/<int:project_id>/finish')
class PorjectFinishApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = Project.query.get(project_id)
        if project.status != 'pending':
            api.abort(
                401, "Project can be set to 'finish' only after creator's upload.")
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if g.current_user.id != project.client_user_id:
                api.abort(
                    403, "Only the project's client can feedback(Administrator privileges required).")
        try:
            project.finish(g.current_user.id)
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_PROJECT.route('/<int:project_id>/discard')
class PorjectDiscardApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = Project.query.get(project_id)
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            api.abort(
                403, "Administrator privileges required for request update action.")
        try:
            project.discard()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_PROJECT.route('/<int:project_id>/resume')
class PorjectResumeApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = Project.query.get(project_id)
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            api.abort(
                403, "Administrator privileges required for request update action.")
        try:
            project.resume()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_PROJECT.route('/<int:project_id>/abnormal')
class PorjectAbnormalApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = Project.query.get(project_id)
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            api.abort(
                403, "Administrator privileges required for request update action.")
        try:
            project.abnormal()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


def projectCheck(project_id):
    project = Project.query.get(project_id)
    if not project:
        api.abort(400, "Project is not exist.")
    else:
        return project
