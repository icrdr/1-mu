from ..model import User, Course, LiveLog
from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from ..utility import buildUrl, getAvatar
from .utility import CourseCheck
from sqlalchemy import or_, case, and_
from .. import api, app, db
from .decorator import permission_required, admin_required


N_COURSE = api.namespace('api/courses', description='Live room Operations')

M_USER = api.model('user', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x), description="The avatar url for the user."),
})

M_LIVE_PUSH_URL = api.model('live_push_urls', {
    'id': fields.Integer(),
    'stream_url': fields.String(),
    'stream_auth': fields.String(),
})

M_LIVE_PULL_URL = api.model('live_pull_urls', {
    'id': fields.Integer(),
    'rtmp_url': fields.String(),
    'flv_url': fields.String(),
    'hls_url': fields.String(),
    'streaming':fields.Boolean()
})

M_COURSE = api.model('course', {
    'id': fields.Integer(),
    'name': fields.String(),
    'excerpt': fields.String(),
    'tutors': fields.List(fields.Nested(M_USER)),
    'current_host': fields.Nested(M_USER, attribute=lambda x: x.live_room.current_host),
    'members_count': fields.Integer(attribute=lambda x: len(x.members)),
    'views_count': fields.Integer(attribute=lambda x: len(x.live_room.current_viewers)),
    'streaming':fields.Boolean(attribute=lambda x: x.live_room.streaming)
})

M_COURSE_INFO = api.model('course', {
    'id': fields.Integer(),
    'name': fields.String(),
    'intro': fields.String(),
    'tutors': fields.List(fields.Nested(M_USER)),
    'members': fields.List(fields.Nested(M_USER)),
    'current_host': fields.Nested(M_USER, attribute=lambda x: x.live_room.current_host),
    'views_count': fields.Integer(attribute=lambda x: len(x.live_room.current_viewers)),
    'live_room': fields.Nested(M_LIVE_PULL_URL)
})


GET_COURSE = reqparse.RequestParser()\
    .add_argument('search', location='args', action='split')\
    .add_argument('include', location='args', action='split')\
    .add_argument('exclude', location='args', action='split')\
    .add_argument('order', location='args', default='desc', choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id',
                  choices=['id', 'name', 'reg_date'])\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)\
    .add_argument('public', type=int)

POST_COURSE = reqparse.RequestParser()\
    .add_argument('name', required=True)\
    .add_argument('tutor_id', type=int, required=True)\
    .add_argument('intro', required=True)


@N_COURSE.route('')
class CourseApi(Resource):
    @api.marshal_with(M_COURSE, envelope='courses')
    def get(self):
        args = GET_COURSE.parse_args()
        query = Course.query

        if args['public'] != None:
            query = query.filter_by(public=args['public'])

        if args['search']:
            query = query.filter(Course.name.contains(args['search']))

        if args['include']:
            if args['exclude']:
                api.abort(400, "include or exclude, not both")
            query = query.filter(Course.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(Course.id.notin_(args['exclude']))

        if args['order_by'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(Course.id.asc())
            else:
                query = query.order_by(Course.id.desc())
        elif args['order_by'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(Course.name.asc(), Course.id.asc())
            else:
                query = query.order_by(Course.name.desc(), Course.id.asc())
        elif args['order_by'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(Course.reg_date.asc())
            else:
                query = query.order_by(Course.reg_date.desc())

        course_list = query.limit(args['pre_page']).offset(
            (args['page']-1)*args['pre_page']).all()

        return course_list, 200

    @api.marshal_with(M_COURSE)
    def post(self):
        args = POST_COURSE.parse_args()
        try:
            new_course = Course.createCourse(
                name=args['name'],
                intro=args['intro'],
                tutor_id=args['tutor_id']
            )
        except Exception as e:
            print(e)
            api.abort(500, '[Sever Error]: ' + str(e))

        return new_course, 200


@N_COURSE.route('/<int:course_id>')
class CourseDetailApi(Resource):
    @api.marshal_with(M_COURSE_INFO)
    # @permission_required()
    def get(self, course_id):
        course = CourseCheck(course_id)
        return course, 201


@N_COURSE.route('/<int:course_id>/ready')
class CourseReadyApi(Resource):
    @api.marshal_with(M_LIVE_PUSH_URL)
    # @permission_required()
    def put(self, course_id):
        course = CourseCheck(course_id)
        try:
            live_room = course.live_room
            live_room.doReady(1)

            return live_room, 201
        except Exception as error:
            print('[Sever Error]: %s' % error)
            api.abort(500, '[Sever Error]: %s' % error)

@N_COURSE.route('/<int:course_id>/end')
class CourseEndApi(Resource):
    @api.marshal_with(M_COURSE_INFO)
    # @permission_required()
    def put(self, course_id):
        course = CourseCheck(course_id)
        try:
            live_room = course.live_room
            live_room.doEnd()
            return course, 201
        except Exception as error:
            print('[Sever Error]: %s' % error)
            api.abort(500, '[Sever Error]: %s' % error)
