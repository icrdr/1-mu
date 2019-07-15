from flask_restplus import Resource, reqparse, fields, marshal
from .. import api, db, scheduler
from ..model import Project, Stage, Phase, User
from ..utility import buildUrl, getAvatar
from datetime import datetime, timedelta
import json

n_porject = api.namespace('api/projects', description='projects operations')

m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
    'format': fields.String(description="Registration date for the user."),
})

m_phase = api.model('phase', {
    'id': fields.Integer,
    'status': fields.String,
    'days_need': fields.Integer,
    'post_date': fields.String,
    'feedback_date': fields.String,
    'creator_post': fields.String,
    'client_feedback': fields.String,
    'files': fields.List(fields.Nested(m_file))
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
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x), description="The avatar url for the user."),
})

m_client = api.model('client', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x), description="The avatar url for the user."),
})

m_project = api.model('project', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'design': fields.String(description="Display name for the user."),
    'creator': fields.Nested(m_creator),
    'client': fields.Nested(m_client),
    'public_date': fields.String(description="Display name for the user."),
    'current_stage_index': fields.Integer(attribute=lambda x: x.current_stage_index),
    'stages': fields.List(fields.Nested(m_stage))
})
m_projects = api.model('projects', {
    'projects': fields.List(fields.Nested(m_project)),
    'total': fields.Integer(description="Unique identifier for the user."),
})

g_project = reqparse.RequestParser()
g_project.add_argument('creator_id', location='args', action='split',
                       help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")
g_project.add_argument('client_id', location='args', action='split',
                       help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")
g_project.add_argument('include', location='args', action='split',
                       help="Limit result set to specific IDs.")
g_project.add_argument('exclude', location='args', action='split',
                       help="Ensure result set excludes specific IDs.")
g_project.add_argument('order', location='args', default='asc',
                       choices=['asc', 'desc'],
                       help="Order sort attribute ascending or descending.")
g_project.add_argument('orderby', location='args', default='id',
                       choices=['id', 'name', 'start_date'],
                       help="Sort collection by object attribute.")
g_project.add_argument('page', location='args', type=int, default=1,
                       help="Current page of the collection.")
g_project.add_argument('pre_page', location='args', type=int, default=10,
                       help="Maximum number of items to be returned in result set.")

p_project = reqparse.RequestParser()
p_project.add_argument('name', location='args', required=True,
                       help="Login name for the user.")
p_project.add_argument('stages', location='args', type=json.loads, action='append', required=True,
                       help="Password for the user (never included).")
p_project.add_argument('creator_id', location='args', type=int, required=True,
                       help="Login name for the user.")
p_project.add_argument('client_id', location='args', type=int, required=True,
                       help="Login name for the user.")

u_project = reqparse.RequestParser()
u_project.add_argument('project_id', location='args', action='split', required=True,
                       help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")
u_project.add_argument('action', location='args', default='start', required=True,
                       choices=['start', 'finish', 'discard','post','modify'],
                       help="Sort collection by object attribute.")
u_project.add_argument('feedback', location='args',
                       help="Login name for the user.")
u_project.add_argument('post', location='args',
                       help="Login name for the user.")
u_project.add_argument('creator_id', location='args', type=int,
                    help="The title for the user.")
u_project.add_argument('client_id', location='args', type=int,
                    help="The title for the user.")

d_project = reqparse.RequestParser()
d_project.add_argument('project_id', location='args', action='split', required=True,
                       help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")

@n_porject.route('')
class PorjectsApi(Resource):
    def get(self):
        args = g_project.parse_args()
        query = Project.query
        if args['creator_id']:
            query = query.filter(
                Project.creator_user_id.in_(args['creator_id']))
        if args['client_id']:
            query = query.filter(Project.client_user_id.in_(args['client_id']))

        if args['include']:
            if args['exclude']:
                api.abort(400, "include or exclude, not both")
            query = query.filter(Project.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(Project.id.notin_(args['exclude']))

        if args['orderby'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(Project.id.asc())
            else:
                query = query.order_by(Project.id.desc())
        elif args['orderby'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(Project.name.asc())
            else:
                query = query.order_by(Project.name.desc())
        elif args['orderby'] == 'start_date':
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
                'projects':projects,
                'total':total
            }
            return marshal(output, m_projects,skip_none=True), 200
        else:
            api.abort(400, "project doesn't exist")

    @api.marshal_with(m_project)
    def post(self):
        args = p_project.parse_args()
        return createProject(args['name'], args['stages'], args['creator_id'], args['client_id'])

    @api.marshal_with(m_project, envelope='projects')
    def put(self):
        args = u_project.parse_args()
        projects = Project.query.filter(
            Project.id.in_(args['project_id'])).all()
        if projects:
            for project in projects:
                # get current stage
                current_stage = project.stages[project.current_stage_index]
                # get current phase
                current_phase = current_stage.phases[-1]

                try:
                    if args['action'] == 'start':
                        # check if project started or not
                        if project.stages[0].phases[0].status != 'await':
                            raise Exception("already started")
                        
                        # start project
                        current_phase.status = 'progress'
                        current_stage.start_date = datetime.utcnow()
                        

                        # create a new delay counter
                        addDelayCounter(current_stage.id, current_phase.days_need)

                    elif args['action'] == 'modify':
                        if current_phase.status != 'pending':
                            raise Exception("it can't modify by now")
                        # current phase update
                        current_phase.client_feedback = args['feedback']
                        current_phase.feedback_date = datetime.utcnow()
                        current_phase.status = 'finish'

                        # craete new phase in current stage
                        new_phase = Phase(
                            parent_stage=current_stage,
                            days_need=4,  # 4 days later
                            status='modify'
                        )
                        db.session.add(new_phase)

                        # create a new delay counter
                        addDelayCounter(current_stage.id, new_phase.days_need)

                    elif args['action'] == 'finish':
                        # current phase update
                        current_phase.client_feedback = args['feedback']
                        current_phase.feedback_date = datetime.utcnow()
                        current_phase.status = 'finish'

                        # if current stage is not the last one, then go into next stage
                        if project.current_stage_index < len(project.stages)-1:
                            # next stage phase update 
                            project.current_stage_index += 1
                            next_stage = project.stages[project.current_stage_index]

                            next_stage.phases[0].status = 'progress'
                            next_stage.start_date = datetime.utcnow()

                            # create a new delay counter
                            new_phase = next_stage.phases[0]
                            addDelayCounter(current_stage.id, new_phase.days_need)
                        else:
                            # stop the old delay counter,
                            removeDelayCounter(current_stage.id)

                    elif args['action'] == 'post':
                        # current phase update
                        current_phase.creator_post = args['post']
                        current_phase.post_date = datetime.utcnow()
                        current_phase.status = 'pending'

                        # stop the delay counter
                        removeDelayCounter(current_stage.id)
                    elif args['action'] == 'discard':
                        # current phase update
                        current_phase.status = 'discard'

                        # stop the delay counter
                        removeDelayCounter(current_stage.id)

                    if args['creator_id']:
                        if User.query.get(args['creator_id']):
                            project.creator_user_id = args['creator_id']
                        else:
                            raise Exception("creator not exist")

                    if args['client_id']:
                        if User.query.get(args['client_id']):
                            project.client_user_id = args['client_id']
                        else:
                            raise Exception("client not exist")

                    db.session.commit()
                except Exception as e:
                    print(e)
                    api.abort(400, e)

            return projects, 200
        else:
            api.abort(400, "project doesn't exist")

    def delete(self):
        args = d_project.parse_args()
        projects = Project.query.filter(Project.id.in_(args['project_id'])).all()
        if projects:
            for project in projects:
                stages = project.stages
                for stage in stages:
                    phases = stage.phases
                    for phase in phases:
                        db.session.delete(phase)
                    db.session.delete(stage)
                db.session.delete(project)

            db.session.commit()
            return {'ok': 'ok'}, 200
        else:
            api.abort(400, "project doesn't exist")

def createProject(name, stages, creator_id, client_id):
    try:
        # create project
        new_project = Project(
            name=name,
            client_user_id=client_id,
            creator_user_id=creator_id
        )
        db.session.add(new_project)

        # create stage
        for i in range(len(stages)):
            new_stage = Stage(
                name=stages[i]['stage_name'],
                parent_project=new_project,
            )
            db.session.add(new_stage)
            new_phase = Phase(
                parent_stage=new_stage,
                days_need=stages[i]['days_need']
            )
            db.session.add(new_phase)
        db.session.commit()
        return new_project
    except Exception as e:
        print(e)
        api.abort(400, "project can't create!")


def delay(stage_id):
    stage = Stage.query.get(stage_id)
    phase = stage.phases[-1]
    phase.status = 'delay'
    db.session.commit()
    print('stage_'+str(stage_id)+': delay!')

def addDelayCounter(stage_id, days_need):
    deadline = datetime.utcnow()+timedelta(days=days_need)
    scheduler.add_job(
        id='stage_delay_' + str(stage_id),
        func=delay,
        args=[stage_id],
        trigger ='date',
        run_date = deadline,
        replace_existing=True
    )

def removeDelayCounter(stage_id):
    try:
        scheduler.remove_job('stage_delay_'+str(stage_id))
    except Exception as e:
        print(e)