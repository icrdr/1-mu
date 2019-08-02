from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db, app
from ..model import File, Stage, Preview, Tag, User, Group

from werkzeug import utils, datastructures
from .decorator import permission_required, admin_required
from datetime import datetime
import os, shortuuid
from ..utility import buildUrl, getAvatar
from psd_tools import PSDImage
from PIL import Image
from sqlalchemy import or_

PERMISSIONS = app.config['PERMISSIONS']

ns_file = api.namespace('api/files', description='upload operations')

m_user = api.model('user', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: getAvatar(x), description="The avatar url for the user."),
})

m_preview = api.model('preview', {
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
})
M_TAG = api.model('tag', {
    'id': fields.Integer,
    'name': fields.String,
})
m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'description': fields.String(description="The title for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
    'format': fields.String(description="Registration date for the user."),
    'uploader': fields.Nested(m_user),
    'previews': fields.List(fields.Nested(m_preview)),
    'tags': fields.List(fields.Nested(M_TAG)),
    'upload_date': fields.String(description="Registration date for the user.")
})

g_file = reqparse.RequestParser()\
    .add_argument('user_id', location='args', action='split')\
    .add_argument('group_id', location='args', action='split')\
    .add_argument('search', location='args', action='split')\
    .add_argument('format', location='args',choices=['png', 'jpg', 'jpeg', 'txt', 'pdf', 'gif'])\
    .add_argument('include', location='args', action='split')\
    .add_argument('exclude', location='args', action='split')\
    .add_argument('order', location='args', default='asc',choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id',
                    choices=['id', 'name', 'reg_date'])\
    .add_argument('page', location='args', type=int, default=1)\
    .add_argument('pre_page', location='args', type=int, default=10)\
    .add_argument('public', type=int)

#formdata can't be list, so here use 'split' action
p_file = reqparse.RequestParser()\
    .add_argument('file', required=True, type=datastructures.FileStorage, location='files')\
    .add_argument('tags', action='split')\
    .add_argument('description')\
    .add_argument('public', type=int, default=0)

@ns_file.route('')
class UploadApi(Resource):
    @api.marshal_with(m_file, envelope='files')
    @api.expect(g_file)
    @permission_required()
    def get(self):
        args = g_file.parse_args()
        query = File.query

        if args['public'] != None:
            query = query.filter_by(public=args['public'])

        if args['user_id']:
            query = query.filter(File.uploader_user_id.in_(args['user_id']))

        if args['group_id']:
            query = query.join(File.uploader).join(User.groups).filter(
                Group.id.in_(args['group_id']))

        if args['format']:
            query = query.filter_by(format=args['format'])

        if args['search']:
            for _str in args['search']:
                query = query.join(File.tags).filter(
                    or_(File.name.contains(_str), Tag.name.contains(_str)))

        if args['include']:
            if args['exclude']:
                api.abort(400, "include or exclude, not both")
            query = query.filter(File.id.in_(args['include']))
        elif args['exclude']:
            query = query.filter(File.id.notin_(args['exclude']))

        if args['order_by'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(File.id.asc())
            else:
                query = query.order_by(File.id.desc())
        elif args['order_by'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(File.name.asc(), File.id.asc())
            else:
                query = query.order_by(File.name.desc(), File.id.asc())
        elif args['order_by'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(File.upload_date.asc())
            else:
                query = query.order_by(File.upload_date.desc())

        files_list = query.paginate(
            args['page'], args['pre_page'], error_out=False).items

        return files_list, 200

    @api.marshal_with(m_file)
    @api.expect(p_file)
    @permission_required(PERMISSIONS['UPLOAD'])
    def post(self):
        args = p_file.parse_args()

        if not allowed_file(args['file'].filename):
            api.abort(400, "file format not allowed!")
        
        uploader_id = 1
        if 'current_user' in g:
            uploader_id = g.current_user.id
        
        try:
            new_file = File.create_file(
                    uploader_id = uploader_id,
                    file=args['file'],
                    description=args['description'],
                    tags=args['tags'],
                    public=args['public'],
                )
        except Exception as e:
            print(e)
            api.abort(500, '[Sever Error]: '+ str(e))

        return new_file, 200
            

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower(
           ) in app.config['ALLOWED_EXTENSIONS']

u_file_tags = reqparse.RequestParser()\
    .add_argument('tags', action='append', required=True)

@ns_file.route('/<int:file_id>/tags/add')
class FileTagAddApi(Resource):
    @api.marshal_with(m_file)
    @permission_required()
    def put(self, file_id):
        args = u_file_tags.parse_args()
        file = fileCheck(file_id)
        for tag in args['tags']:
            _tag = Tag.query.filter_by(name=tag).first()
            if not _tag:
                _tag = Tag(name=tag)
                db.session.add(_tag)
            if _tag not in file.tags:
                file.tags.append(_tag)

        db.session.commit()
        return file, 200

def fileCheck(file_id):
    file = File.query.get(file_id)
    if not file:
        api.abort(400, "file is not exist.")
    else:
        return file