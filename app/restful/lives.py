from ..model import User, LiveRoom, LiveLog
from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from ..utility import buildUrl, getAvatar
from .utility import liveRoomCheck
from sqlalchemy import or_, case, and_
from .. import api, app, db
from .decorator import permission_required, admin_required

N_LIVE = api.namespace('api/lives', description='Live room Operations')

M_USER = api.model('user', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x), description="The avatar url for the user."),
})


M_LIVE_ROOM = api.model('live_room', {
    'id': fields.Integer(),
    'name': fields.String(),
    'description': fields.String(),
    'steam_url': fields.String(),
    'steam_auth': fields.String(),
    'rtmp_url': fields.String(),
    'flv_url': fields.String(),
    'hls_url': fields.String(),
    'hosts': fields.List(fields.Nested(M_USER)),
    'admins': fields.List(fields.Nested(M_USER)),
    'current_host': fields.List(fields.Nested(M_USER)),
    'views_count': fields.Integer(attribute=lambda x: len(x.current_viewers))
})

M_LIVE_ROOM_URL = api.model('live_room_urls', {
    'id': fields.Integer(),
    'name': fields.String(),
    'steam_url': fields.String(),
    'steam_auth': fields.String(),
    'rtmp_url': fields.String(),
    'flv_url': fields.String(),
    'hls_url': fields.String()
})

GET_LIVE_ROOM = reqparse.RequestParser()\
    .add_argument('current_host_ids', location='args', action='split')\
    .add_argument('search', location='args', action='split')\
    .add_argument('include', location='args', action='split')\
    .add_argument('exclude', location='args', action='split')\
    .add_argument('order', location='args', default='asc', choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id',
                  choices=['id', 'name', 'reg_date'])\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)\
    .add_argument('public', type=int)

POST_LIVE_ROOM = reqparse.RequestParser()\
    .add_argument('name', required=True)\
    .add_argument('host_id', type=int, required=True)\
    .add_argument('description', required=True)

@N_LIVE.route('')
class LiveRoomApi(Resource):
    @api.marshal_with(M_LIVE_ROOM, envelope='live_rooms')
    def get(self):
        args = GET_LIVE_ROOM.parse_args()
        query = LiveRoom.query

        if args['public'] != None:
            query = query.filter_by(public=args['public'])

        if args['current_host_ids']:
            query = query.filter(LiveRoom.current_host_id.in_(args['current_host_ids']))

        if args['search']:
            query = query.filter(LiveRoom.name.contains(args['search']))

        if args['include']:
            if args['exclude']:
                api.abort(400, "include or exclude, not both")
            query = query.filter(LiveRoom.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(LiveRoom.id.notin_(args['exclude']))

        if args['order_by'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(LiveRoom.id.asc())
            else:
                query = query.order_by(LiveRoom.id.desc())
        elif args['order_by'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(LiveRoom.name.asc(), LiveRoom.id.asc())
            else:
                query = query.order_by(LiveRoom.name.desc(), LiveRoom.id.asc())
        elif args['order_by'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(LiveRoom.reg_date.asc())
            else:
                query = query.order_by(LiveRoom.reg_date.desc())

        rooms_list = query.limit(args['pre_page']).offset((args['page']-1)*args['pre_page']).all()

        return rooms_list, 200

    @api.marshal_with(M_LIVE_ROOM)
    def post(self):
        args = POST_LIVE_ROOM.parse_args()
        try:
            new_live_room = LiveRoom.createLiveRoom(
                name=args['name'],
                description=args['description'],
                host_id=args['host_id']
            )
        except Exception as e:
            print(e)
            api.abort(500, '[Sever Error]: ' + str(e))

        return new_live_room, 200

@N_LIVE.route('/<int:live_room_id>/ready')
class LiveRoomReadyApi(Resource):
    @api.marshal_with(M_LIVE_ROOM_URL)
    # @permission_required()
    def put(self, live_room_id):
        live_room = liveRoomCheck(live_room_id)

        try:
            live_room.doReady(1)
            return live_room, 201
        except Exception as error:
            print('[Sever Error]: %s' % error)
            api.abort(500, '[Sever Error]: %s' % error)