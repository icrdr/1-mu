from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db, app
from ..model import File, Stage, Preview

from werkzeug import utils, datastructures
from .decorator import permission_required, admin_required
from datetime import datetime
import os, shortuuid
from ..utility import buildUrl, getAvatar
from psd_tools import PSDImage
from PIL import Image

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

m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'description': fields.String(description="The title for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
    'format': fields.String(description="Registration date for the user."),
    'uploader': fields.Nested(m_user),
    'previews': fields.List(fields.Nested(m_preview)),
    'upload_date': fields.String(description="Registration date for the user.")
})

g_file = reqparse.RequestParser()
g_file.add_argument('user_id', location='args', action='split',
                    help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")
g_file.add_argument('format', location='args',
                    choices=['png', 'jpg', 'jpeg', 'txt', 'pdf', 'gif'],
                    help="Order sort attribute ascending or descending.")
g_file.add_argument('include', location='args', action='split',
                    help="Limit result set to specific IDs.")
g_file.add_argument('exclude', location='args', action='split',
                    help="Ensure result set excludes specific IDs.")
g_file.add_argument('order', location='args', default='asc',
                    choices=['asc', 'desc'],
                    help="Order sort attribute ascending or descending.")
g_file.add_argument('order_by', location='args', default='id',
                    choices=['id', 'name', 'reg_date'],
                    help="Sort collection by object attribute.")
g_file.add_argument('page', location='args', type=int, default=1,
                    help="Current page of the collection.")
g_file.add_argument('pre_page', location='args', type=int, default=10,
                    help="Maximum number of items to be returned in result set.")

p_file = reqparse.RequestParser()\
    .add_argument('file', required=True, type=datastructures.FileStorage, location='files')\
    .add_argument('tags', action='append')\
    .add_argument('public', type=int, default=0)


@ns_file.route('')
class UploadApi(Resource):
    @api.marshal_with(m_file, envelope='files')
    @api.expect(g_file)
    @permission_required()
    def get(self):
        args = g_file.parse_args()
        query = File.query
        if args['user_id']:

            query = query.filter(File.uploader_user_id.in_(args['user_id']))
        if args['format']:
            query = query.filter_by(format=args['format'])

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
                query = query.order_by(File.name.asc())
            else:
                query = query.order_by(File.name.desc())
        elif args['order_by'] == 'reg_date':
            if args['order'] == 'asc':
                query = query.order_by(File.upload_date.asc())
            else:
                query = query.order_by(File.upload_date.desc())

        files_list = query.paginate(
            args['page'], args['pre_page'], error_out=False).items

        if(files_list):
            return files_list, 200
        else:
            api.abort(400, "file doesn't exist")

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