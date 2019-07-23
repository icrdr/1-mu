from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from .. import api, db, scheduler
from ..model import Project, Stage, Phase, User, File, PERMISSIONS
from ..utility import buildUrl, getAvatar
from datetime import datetime, timedelta
from .decorator import permission_required, admin_required
import json

n_porject = api.namespace('api/projects', description='projects operations')

m_preview = api.model('preview', {
    'url': fields.String(attribute=lambda x: buildUrl(x.url)),
})

m_file = api.model('file', {
    'id': fields.Integer,
    'name': fields.String,
    'url': fields.String(attribute=lambda x: buildUrl(x.url)),
    'format': fields.String,
    'previews': fields.List(fields.Nested(m_preview)),
})

m_phase = api.model('phase', {
    'id': fields.Integer,
    'days_need': fields.Integer,
    'upload_date': fields.String,
    'feedback_date': fields.String,
    'creator_upload': fields.String,
    'client_feedback': fields.String,
    'upload_files': fields.List(fields.Nested(m_file))
})

m_stage = api.model('stage', {
    'id': fields.Integer,
    'name': fields.String,
    'start_date': fields.String,
    'phases': fields.List(fields.Nested(m_phase))
})

m_creator = api.model('creator', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x)),
})

m_client = api.model('client', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x)),
})

m_project = api.model('project', {
    'id': fields.Integer,
    'title': fields.String,
    'design': fields.String,
    'status': fields.String,
    'creators': fields.List(fields.Nested(m_creator)),
    'client': fields.Nested(m_client),
    'public_date': fields.String,
    'start_date': fields.String,
    'finish_date': fields.String,
    'current_stage_index': fields.Integer,
    'stages': fields.List(fields.Nested(m_stage)),
})
m_projects = api.model('projects', {
    'projects': fields.List(fields.Nested(m_project)),
    'total': fields.Integer,
})

g_project = reqparse.RequestParser()
g_project.add_argument('creator_id', location='args', action='split')
g_project.add_argument('client_id', location='args', action='split')
g_project.add_argument('status', location='args', action='split')
g_project.add_argument('include', location='args', action='split')
g_project.add_argument('exclude', location='args', action='split')
g_project.add_argument('page', location='args', type=int, default=1)
g_project.add_argument('pre_page', location='args', type=int, default=10)
g_project.add_argument('order', location='args', default='asc',
                       choices=['asc', 'desc'])
g_project.add_argument('order_by', location='args', default='id',
                       choices=['id', 'title', 'start_date'])

p_project = reqparse.RequestParser()
p_project.add_argument('title', required=True)
p_project.add_argument('stages', type=list, location='json', required=True)
p_project.add_argument('creators', type=int, action='append', required=True)
p_project.add_argument('client_id', type=int, required=True)
p_project.add_argument('design', required=True)

u_project = reqparse.RequestParser()
u_project.add_argument('action', default='none',
                       choices=['none', 'start', 'finish', 'discard', 'upload', 'modify', 'resume', 'abnormal'])
u_project.add_argument('feedback')
u_project.add_argument('upload')
u_project.add_argument('upload_files', type=list, location='json')
u_project.add_argument('client_id', type=int)
u_project.add_argument('creators', type=int, action='append')


@n_porject.route('')
class PorjectsApi(Resource):
    @api.expect(g_project)
    def get(self):
        args = g_project.parse_args()
        query = Project.query
        if args['creator_id']:
            query = query.join(Project.creators).filter(User.id.in_(args['creator_id']))
        if args['client_id']:
            query = query.filter(Project.client_user_id.in_(args['client_id']))

        if args['status']:
            query = query.filter(Project.status.in_(args['status']))

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

        if(projects):
            output = {
                'projects': projects,
                'total': total
            }
            return marshal(output, m_projects, skip_none=True), 200
        else:
            api.abort(400, "projects doesn't exist")

    @api.marshal_with(m_project)
    @api.expect(p_project)
    @permission_required()
    def post(self):
        args = p_project.parse_args()
        # permission checking
        if not User.query.get(args['client_id']):
            return api.abort(401, "Client is not exist.")
        for creator_id in args['creators']:
            if not User.query.get(creator_id):
                return api.abort(401, "Creator is not exist.")
        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if (not g.current_user.id in args['creators']):
                return api.abort(403, "Poster must be one of the creators(Administrator privileges required).")

        try:
            # create project
            new_project = Project(
                title=args['title'],
                client_user_id=args['client_id'],
                design=args['design']
            )
            db.session.add(new_project)
            new_project.status='await'
            for creator_id in args['creators']:
                creator = User.query.get(creator_id)
                new_project.creators.append(creator)

            # create stage
            for stage in args['stages']:
                new_stage = Stage(
                    name=stage['stage_name'],
                    parent_project=new_project,
                )
                db.session.add(new_stage)
                new_phase = Phase(
                    parent_stage=new_stage,
                    days_need=stage['days_need']
                )
                db.session.add(new_phase)
            db.session.commit()
            return new_project, 201
        except Exception as e:
            print(e)
            api.abort(500, '[Sever Error]: '+ str(e))


@n_porject.route('/<int:id>')
class PorjectApi(Resource):
    @api.marshal_with(m_project)
    def get(self, id):
        if not Project.query.get(id):
            return api.abort(400, "Project is not exist.")
        return Project.query.get(id), 200
    
    @api.marshal_with(m_project)
    @api.expect(u_project)
    @permission_required()
    def put(self, id):
        args = u_project.parse_args()
        if not Project.query.get(id):
            return api.abort(400, "Project is not exist.")
        project = Project.query.get(id)
        if args['client_id']:
            if not User.query.get(args['client_id']):
                return api.abort(401, "Client is not exist.")
        if args['creators']:
            for creator_id in args['creators']:
                if not User.query.get(creator_id):
                    return api.abort(401, "Creator is not exist.")
        if args['upload_files']:
            for upload_file in args['upload_files']:
                if not File.query.get(upload_file['id']):
                    return api.abort(401, "File is not exist.")

        if args['action'] == 'start':
            if project.status != 'await':
                return api.abort(401, "Project is already started.")
        elif args['action'] == 'modify':
            if project.status != 'pending':
                return api.abort(401, "Project can be set to 'modify' only after creator's upload.")
        elif args['action'] == 'finish':
            if project.status != 'pending':
                return api.abort(401, "Project can be set to 'finish' only after creator's upload.")
        elif args['action'] == 'upload':
            if project.status != 'modify' and project.status != 'progress':
                return api.abort(401, "Creator can upload only during 'modify' or 'progress'.")

        if not g.current_user.can(PERMISSIONS['ADMIN']):
            if args['action'] == 'resume' or args['action'] == 'abnormal' or args['action'] == 'discard':
                return api.abort(403, "Administrator privileges required for request update action.")
            if g.current_user.id != project.client_user_id:
                if args['feedback']!=None or args['action'] == 'modify' or args['action'] == 'finish':
                    return api.abort(403, "Only the project's client can feedback(Administrator privileges required).")
                if args['action'] == 'start':
                    return api.abort(403, "Only the project's client can start(Administrator privileges required).")
            if not g.current_user in project.creators:
                if args['upload']!=None or args['action'] == 'upload' or args['upload_files']:
                    return api.abort(403, "Only the project's creator can upload(Administrator privileges required).")

        # get current stage
        current_stage = project.stages[project.current_stage_index]
        # get current phase
        current_phase = current_stage.phases[-1]

        try:
            if args['action'] == 'start':
                # start project
                project.status = 'progress'
                project.start_date = datetime.utcnow()
                current_stage.start_date = datetime.utcnow()
                # create a new delay counter
                addDelayCounter(current_stage.id, current_phase.days_need)

            elif args['action'] == 'modify':
                # current phase update
                project.status = 'modify'
                current_phase.feedback_date = datetime.utcnow()
                current_phase.client_user_id = g.current_user.id
                # craete new phase in current stage
                new_phase = Phase(
                    parent_stage=current_stage,
                    days_need=4,  # 4 days later
                )
                db.session.add(new_phase)

                # create a new delay counter
                addDelayCounter(current_stage.id, new_phase.days_need)
            elif args['action'] == 'finish':
                # current phase update
                project.status = 'finish'
                current_phase.feedback_date = datetime.utcnow()
                current_phase.client_user_id = g.current_user.id
                nextStageStart(project)

            elif args['action'] == 'upload':
                # current phase update
                project.status = 'pending'
                current_phase.upload_date = datetime.utcnow()
                current_phase.creator_user_id = g.current_user.id

                # stop the delay counter
                removeDelayCounter(current_stage.id)
            elif args['action'] == 'discard':
                # current phase update
                project.status = 'discard'
                project.last_pause_date = datetime.utcnow()
                # stop the delay counter
                removeDelayCounter(current_stage.id)
            elif args['action'] == 'abnormal':
                # current phase update
                project.status = 'abnormal'
                project.last_pause_date = datetime.utcnow()
                # stop the delay counter
                removeDelayCounter(current_stage.id)
            elif args['action'] == 'resume':
                # current phase update
                if current_phase.feedback_date:
                    project.status = 'finish'
                    nextStageStart(project)
                elif current_phase.upload_date:
                    project.status = 'pending'
                elif current_stage.start_date:
                    if len(current_stage.phases) > 1:
                        project.status = 'modify'
                    else:
                        project.status = 'progress'
                    # create a new delay counter
                    addDelayCounter(
                        current_stage.id, current_phase.days_need,
                        offset=current_stage.start_date - project.last_pause_date
                    )
                else:
                    project.status = 'await'

            # other update
            if args['upload']!=None:
                current_phase.creator_upload = args['upload']

            if args['feedback']!=None:
                current_phase.client_feedback = args['feedback']

            if args['upload_files']!=None:
                current_phase.upload_files=[]
                for upload_file in args['upload_files']:
                    current_phase.upload_files.append(
                        File.query.get(upload_file['id']))

            if args['client_id']!=None:
                project.client_user_id = args['client_id']

            db.session.commit()
            return project, 201
        except Exception as e:
            print(e)
            api.abort(500, '[Sever Error]: ' + str(e))

    @admin_required
    def delete(self, id):
        if not Project.query.get(id):
            return api.abort(400, "Project is not exist.")

        project = Project.query.get(id)
        stages = project.stages
        for stage in stages:
            phases = stage.phases
            for phase in phases:
                db.session.delete(phase)
            db.session.delete(stage)
        db.session.delete(project)
        removeDelayCounter(id)

        db.session.commit()
        return {'message': 'ok'}, 204

def nextStageStart(project):
    # if current stage is not the last one, then go into next stage
    if project.current_stage_index < len(project.stages)-1:
        # next stage phase update
        project.current_stage_index += 1
        next_stage = project.stages[project.current_stage_index]

        project.status = 'progress'
        next_stage.start_date = datetime.utcnow()

        # create a new delay counter
        new_phase = next_stage.phases[0]
        addDelayCounter(next_stage.id, new_phase.days_need)
    else:
        project.finish_date = datetime.utcnow()

def delay(project_id):
    project = Project.query.get(project_id)
    if project.status == 'modify' or project.status == 'progress':
        project.status = 'delay'
    db.session.commit()
    print('project_'+str(project_id)+': delay!')


def addDelayCounter(project_id, days_need, offset=timedelta(microseconds=0)):

    deadline = datetime.utcnow()+timedelta(days=days_need) + offset
    scheduler.add_job(
        id='delay_project_' + str(project_id),
        func=delay,
        args=[project_id],
        trigger='date',
        run_date=deadline,
        replace_existing=True
    )
    print('addCounter: '+str(project_id))


def removeDelayCounter(project_id):
    if scheduler.get_job('delay_project_'+str(project_id)):
        scheduler.remove_job('delay_project_'+str(project_id))
        print('removeCounter: '+str(project_id))
