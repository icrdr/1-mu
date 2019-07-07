from flask_restplus import Resource, reqparse, fields
from .. import api, db, scheduler
from ..model import Project, Stage
from ..utility import buildUrl
from datetime import datetime

n_porject = api.namespace('api/project', description='projects operations')

m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
    'format': fields.String(description="Registration date for the user."),
})

m_stage = api.model('stage', {
    'id': fields.Integer,
    'name': fields.String,
    'status': fields.String,
    'deadline_date': fields.String,
    'files': fields.List(fields.Nested(m_file))
})

m_creator = api.model('creator', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(description="The avatar url for the user."),
})

m_client = api.model('client', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(description="The avatar url for the user."),
})

m_project = api.model('project', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'status': fields.String,
    'creator': fields.Nested(m_creator),
    'client': fields.Nested(m_client),
    'stages': fields.List(fields.Nested(m_stage))
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

p_project.add_argument('stage_dates', location='args', action='split', required=True,
                       help="Password for the user (never included).")


@n_porject.route('')
class PorjectsApi(Resource):
    @api.marshal_with(m_project, envelope='projects')
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

        projects_list = query.paginate(
            args['page'], args['pre_page'], error_out=False).items

        if(projects_list):
            return projects_list, 200
        else:
            api.abort(400, "project doesn't exist")

    @api.marshal_with(m_project)
    def post(self):
        args = p_project.parse_args()
        try:
            new_project = Project(
                name=args['name'],
            )
            db.session.add(new_project)
            db.session.commit()
            print(args['stage_dates'])
            try:
                for i in range(len(args['stage_dates'])):
                    date_str = args['stage_dates'][i].split('-')
                    date_obj = datetime(int(date_str[0]), int(date_str[1]), int(date_str[2]))
                    new_stage = Stage(
                        name=args['name']+'_stage'+str(i+1),
                        parent_project_id = new_project.id,
                        deadline_date = date_obj
                    )
                    db.session.add(new_stage)
                db.session.commit()
            except Exception as e:
                print(e)
                db.session.delete(new_project)
                db.session.commit()
                api.abort(400, "project can't create!")
            return new_project
        except Exception as e:
            print(e)
            api.abort(400, "project can't create!")

@n_porject.route('/<int:id>')
class PorjectApi(Resource):
    def delete(self, id):
        project = Project.query.get(id)
        
        if project:
            stages = project.stages
            for stage in stages:
                db.session.delete(stage)
            db.session.delete(project)
            db.session.commit()
            return {'ok': 'ok'},200
        else:
            api.abort(400, "project doesn't exist")

n_test = api.namespace('api/test', description='projects operations')
d_test = reqparse.RequestParser()
d_test.add_argument('name', location='args', required=True,
                       help="Login name for the user.")

def task1(a,b):
    print('sefsefsefsefsefsef')

@n_test.route('')
class TestsApi(Resource):
    def post(self):
        scheduler.add_job(
            id='slkdjflksef', 
            func=task1, 
            args=(1, 2), 
            trigger='date', 
            run_date=datetime(2019, 7, 7, 6, 44, 0),
            misfire_grace_time=3600, 
            )
        return {'message':'ok'}

    def delete(self):
        args = d_test.parse_args()
        scheduler.delete_job(args['name'])
        return {'message':'ok'}
    

# @n_test.route('/<int:id>')


