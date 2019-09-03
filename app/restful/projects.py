"""
Project Api
"""
from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from sqlalchemy import or_, case, and_
from .. import api, app, db
from ..model import Stage, Phase, User, File, Project, Tag, Group
from ..utility import buildUrl, getAvatar
from .decorator import permission_required, admin_required
import time
from datetime import datetime

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

M_PAUSE = api.model('pause', {
    'id': fields.Integer,
    'pause_date': fields.String,
    'resume_date': fields.String,
})

M_PHASE = api.model('phase', {
    'id': fields.Integer,
    'days_need': fields.Integer,
    'upload_date': fields.String,
    'feedback_date': fields.String,
    'start_date': fields.String,
    'deadline_date': fields.String,
    'creator_upload': fields.String,
    'creator': fields.Nested(M_UPLOADER),
    'client': fields.Nested(M_UPLOADER),
    'client_feedback': fields.String,
    'upload_files': fields.List(fields.Nested(M_FILE)),
    'pauses': fields.List(fields.Nested(M_PAUSE))
})

M_STAGE = api.model('stage', {
    'id': fields.Integer,
    'name': fields.String,
    'phases': fields.List(fields.Nested(M_PHASE))
})
M_GROUP = api.model('group', {
    'id': fields.Integer,
    'name': fields.String,
    'admins': fields.List(fields.Nested(M_CREATOR)),
    'users': fields.List(fields.Nested(M_CREATOR))
})
M_PROJECT = api.model('project', {
    'id': fields.Integer,
    'title': fields.String,
    'design': fields.String,
    'remark': fields.String,
    'status': fields.String,
    'creator': fields.Nested(M_CREATOR),
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
    .add_argument('group_id', location='args', action='split')\
    .add_argument('client_id', location='args', action='split')\
    .add_argument('title', location='args')\
    .add_argument('search', location='args')\
    .add_argument('tags', location='args')\
    .add_argument('start_date', location='args', action='split')\
    .add_argument('finish_date', location='args', action='split')\
    .add_argument('current_stage_index', location='args', action='split')\
    .add_argument('status', location='args', action='split')\
    .add_argument('include', location='args', action='split')\
    .add_argument('exclude', location='args', action='split')\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)\
    .add_argument('order', location='args', default='asc', choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id', choices=['id', 'title', 'start_date', 'finish_date', 'status', 'creator_id', 'client_id', 'current_stage_index'])

POST_PROJECT = reqparse.RequestParser()\
    .add_argument('title', required=True)\
    .add_argument('group_id', type=int)\
    .add_argument('creator_id', type=int, required=True)\
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
            query = query.filter(
                Project.creator_user_id.in_(args['creator_id']))

        if args['group_id']:
            query = query.filter(
                Project.creator_group_id.in_(args['group_id']))

        if args['client_id']:
            query = query.filter(Project.client_user_id.in_(args['client_id']))

        if args['title']:
            query = query.filter(Project.title.contains(args['title']))

        if args['status']:
            query = query.filter(Project.status.in_(args['status']))

        if args['start_date']:
            start = datetime.strptime(
                args['start_date'][0], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(args['start_date'][1], '%Y-%m-%d %H:%M:%S')

            query = query.filter(
                and_(Project.start_date <= end, Project.start_date >= start))

        if args['finish_date']:
            start = datetime.strptime(
                args['finish_date'][0], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(
                args['finish_date'][1], '%Y-%m-%d %H:%M:%S')

            query = query.filter(
                and_(Project.finish_date <= end, Project.finish_date >= start))

        if args['current_stage_index']:
            query = query.filter(Project.current_stage_index.in_(
                args['current_stage_index']))

        if args['search']:
            query = query.join(Project.tags).filter(
                or_(Project.title.contains(args['search']), Tag.name.contains(args['search'])))

        if args['tags']:
            query = query.join(Project.tags).filter(
                Tag.name.contains(args['tags']))

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
                query = query.order_by(Project.title.asc(), Project.id.desc())
            else:
                query = query.order_by(Project.title.desc(), Project.id.desc())

        elif args['order_by'] == 'start_date':
            if args['order'] == 'asc':
                query = query.order_by(Project.start_date.asc())
            else:
                query = query.order_by(Project.start_date.desc())
        elif args['order_by'] == 'finish_date':
            if args['order'] == 'asc':
                query = query.order_by(Project.finish_date.asc())
            else:
                query = query.order_by(Project.finish_date.desc())
        elif args['order_by'] == 'status':
            if args['order'] == 'asc':
                query = query.order_by(Project.status.asc(), Project.id.desc())
            else:
                query = query.order_by(
                    Project.status.desc(), Project.id.desc())

        elif args['order_by'] == 'current_stage_index':
            if args['order'] == 'asc':
                query = query.order_by(Project.current_stage_index.asc(
                ), Project.status.desc(), Project.id.desc())
            else:
                query = query.order_by(Project.current_stage_index.desc(
                ), Project.status.desc(), Project.id.desc())

        elif args['order_by'] == 'creator_id':
            if args['order'] == 'asc':
                query = query.join(Project.creator).order_by(
                    User.id.asc(), Project.status.desc(), Project.id.desc())
            else:
                query = query.join(Project.creator).order_by(
                    User.id.desc(), Project.status.desc(), Project.id.desc())

        elif args['order_by'] == 'client_id':
            if args['order'] == 'asc':
                query = query.join(Project.client).order_by(
                    User.id.asc(), Project.status.desc(), Project.id.desc())
            else:
                query = query.join(Project.client).order_by(
                    User.id.desc(), Project.status.desc(), Project.id.desc())

        total = len(query.all())
        projects = query.limit(args['pre_page']).offset(
            (args['page']-1)*args['pre_page']).all()
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
        if not g.current_user.can(PERMISSIONS['EDIT']):
            api.abort(
                403, "Poster must be one of the creators(Administrator privileges required).")
        if not User.query.get(args['client_id']):
            api.abort(401, "Client is not exist.")
        if not User.query.get(args['creator_id']):
            api.abort(401, "Creator is not exist.")

        try:
            new_project = Project.create_project(
                title=args['title'],
                client_id=args['client_id'],
                creator_id=args['creator_id'],
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
    .add_argument('creator_id', type=int)\
    .add_argument('client_id', type=int, )\
    .add_argument('design')\
    .add_argument('remark')\
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
                api.abort(401, "Client is not exist.")
        if args['creator_id']:
            if not User.query.get(args['creator_id']):
                api.abort(401, "Creator is not exist.")
        if args['group_id']:
            if not Group.query.get(args['group_id']):
                api.abort(401, "Group is not exist.")

        try:
            if args['client_id'] != None:
                project.client_user_id = args['client_id']
            if args['creator_id'] != None:
                project.creator_user_id = args['creator_id']
            if args['title'] != None:
                project.title = args['title']
            if args['design'] != None:
                project.design = args['design']
            if args['remark'] != None:
                project.remark = args['remark']

            if args['files']:
                project.files = []
                for file_id in args['files']:
                    file = File.query.get(file_id)
                    project.files.append(file)

            db.session.commit()
            print(project.creator_user_id)
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
        if not g.current_user.can(PERMISSIONS['EDIT']):
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
        if project.status != 'modify' and project.status != 'progress' and project.status != 'delay':
            api.abort(
                401, "Creator can upload only during 'modify' or 'progress'.")
        if not g.current_user.can(PERMISSIONS['EDIT']):
            if g.current_user.id != project.creator_user_id:
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
        if not g.current_user.can(PERMISSIONS['EDIT']):
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


POSTPONE_PROJECT = reqparse.RequestParser()\
    .add_argument('days', type=int, required=True)


@N_PROJECT.route('/<int:project_id>/postpone')
class PorjectPostponeApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        args = POSTPONE_PROJECT.parse_args()
        project = Project.query.get(project_id)
        if project.status != 'modify' and project.status != 'progress' and project.status != 'delay':
            api.abort(
                401, "Creator can upload only during 'modify' or 'progress'.")
        if not g.current_user.can(PERMISSIONS['EDIT']):
            if g.current_user.id != project.client_user_id:
                api.abort(
                    403, "Only the project's client can feedback(Administrator privileges required).")

        try:
            project.postpone(args['days'])
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


FINISH_PROJECT = reqparse.RequestParser()\
    .add_argument('feedback', default='没有建议')\

@N_PROJECT.route('/<int:project_id>/finish')
class PorjectFinishApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        args = FINISH_PROJECT.parse_args()
        project = Project.query.get(project_id)
        if project.status != 'pending':
            api.abort(
                401, "Project can be set to 'finish' only after creator's upload.")
        if not g.current_user.can(PERMISSIONS['EDIT']):
            if g.current_user.id != project.client_user_id:
                api.abort(
                    403, "Only the project's client can feedback(Administrator privileges required).")
        try:
            project.finish(g.current_user.id, args['feedback'])
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
        if not g.current_user.can(PERMISSIONS['EDIT']):
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
        if not g.current_user.can(PERMISSIONS['EDIT']):
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
        if not g.current_user.can(PERMISSIONS['EDIT']):
            api.abort(
                403, "Administrator privileges required for request update action.")
        try:
            project.abnormal()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_PROJECT.route('/<int:project_id>/pause')
class PorjectPauseApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = Project.query.get(project_id)
        if not g.current_user.can(PERMISSIONS['EDIT']):
            api.abort(
                403, "Administrator privileges required for request update action.")
        try:
            project.pause()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


@N_PROJECT.route('/<int:project_id>/back')
class PorjectgoBackApi(Resource):
    @api.marshal_with(M_PROJECT)
    @permission_required()
    def put(self, project_id):
        project = Project.query.get(project_id)
        if not g.current_user.can(PERMISSIONS['EDIT']):
            api.abort(
                403, "Administrator privileges required for request update action.")
        try:
            project.goBack()
            return project, 201
        except Exception as error:
            print(error)
            api.abort(500, '[Sever Error]: ' + str(error))


N_DASH = api.namespace('api/dashboard', description='projects operations')

GET_DASH = reqparse.RequestParser()\
    .add_argument('finish_date', required=True,location='args', action='split')\

@N_DASH.route('/<int:user_id>')
class DashboardApi(Resource):
    def get(self, user_id):
        args = GET_DASH.parse_args()
        user = userCheck(user_id)

        start = datetime.strptime(
            args['finish_date'][0], '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(
            args['finish_date'][1], '%Y-%m-%d %H:%M:%S')

        projects = Project.query.join(Project.phases)\
            .filter(Project.status == 'finish')\
            .filter(and_(Project.finish_date <= end, Project.finish_date >= start))\
            .filter(Phase.creator_user_id == user_id).all()

        stages = Stage.query.join(Stage.phases).join(Stage.parent_project)\
            .filter(Project.status == 'finish')\
            .filter( and_(Project.finish_date <= end, Project.finish_date >= start))\
            .filter(Phase.creator_user_id == user_id).all()

        phases = Phase.query.join(Phase.parent_project)\
            .filter(Project.status == 'finish')\
            .filter(and_(Project.finish_date <= end, Project.finish_date >= start))\
            .filter(Phase.creator_user_id == user_id).all()

        overtime = 0
        for phase in phases:
            duration = phase.upload_date - phase.deadline_date
            duration_in_s = int(duration.total_seconds())
            if duration_in_s > 0:
                overtime += duration_in_s

        return {
            'done_overtime': overtime,
            'done_phases': len(phases),
            'done_stages': len(stages),
            'done_projects': len(projects)
        }, 200


def projectCheck(project_id):
    project = Project.query.get(project_id)
    if not project:
        api.abort(400, "Project is not exist.")
    else:
        return project


def userCheck(user_id):
    user = User.query.get(user_id)
    if not user:
        api.abort(400, "user is not exist.")
    else:
        return user
