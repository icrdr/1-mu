from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db, app
from ..model import File, PERMISSIONS, Stage, Preview

from werkzeug import utils, datastructures
from .decorator import permission_required, admin_required
from datetime import datetime
import os, shortuuid
from ..utility import buildUrl
from psd_tools import PSDImage
from PIL import Image

ns_file = api.namespace('api/file', description='upload operations')

m_wx_user = api.model('user', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'nickname': fields.String(description="Display name for the user."),
    'headimg_url': fields.String(description="The avatar url for the user."),
})

m_user = api.model('user', {
    'id': fields.Integer,
    'name': fields.String,
    'avatar_url': fields.String(attribute=lambda x: buildUrl(x.avatar_url), description="The avatar url for the user."),
    'wx_user': fields.Nested(m_wx_user),
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
    'previews': fields.Nested(m_preview),
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
g_file.add_argument('orderby', location='args', default='id',
                    choices=['id', 'name', 'reg_date'],
                    help="Sort collection by object attribute.")
g_file.add_argument('page', location='args', type=int, default=1,
                    help="Current page of the collection.")
g_file.add_argument('pre_page', location='args', type=int, default=10,
                    help="Maximum number of items to be returned in result set.")

p_file = reqparse.RequestParser()
p_file.add_argument('stage_id', location='args', type=int,
                    help="Maximum number of items to be returned in result set.")
p_file.add_argument('file', required=True, type=datastructures.FileStorage, location='files')


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

        if args['orderby'] == 'id':
            if args['order'] == 'asc':
                query = query.order_by(File.id.asc())
            else:
                query = query.order_by(File.id.desc())
        elif args['orderby'] == 'name':
            if args['order'] == 'asc':
                query = query.order_by(File.name.asc())
            else:
                query = query.order_by(File.name.desc())
        elif args['orderby'] == 'reg_date':
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
        stage = None
        if args['stage_id']:
            stage = Stage.query.get(args['stage_id'])

        file = args['file']
        if allowed_file(file.filename):
            # try:
                # filename = utils.secure_filename(file.filename)
            format = file.filename.split(".")[-1]
            rawname = file.filename[:-len(format)-1]

            date = datetime.utcnow().strftime("%Y%m%d")
            year = date[:4]
            month = date[4:6]
            day = date[6:8]
            random_name = str(shortuuid.uuid())
            filename = random_name +'.'+ format
            path = os.path.join(app.config['UPLOAD_FOLDER'], year, month, day)

            if not os.path.exists(path):
                os.makedirs(path)

            file.save(os.path.join(path, filename))
            
            new_file = File(
                uploader_user_id = g.current_user.id,
                name = rawname,
                format = format,
                url = str(os.path.join(year, month, day , filename)).replace('\\', '/')
            )
            
            if stage:new_file.stages.append(stage)

            db.session.add(new_file)
            db.session.commit()

            if format=='psd':
                psd = PSDImage.open(os.path.join(path, filename))
                psd.compose().save(os.path.join(path, random_name+'.png'))

            if format in ['png','jpg','psd']:
                im_path = ''
                if format=='psd':
                    im_path = os.path.join(path, filename)
                else:
                    im_path = os.path.join(path, random_name+'.png')
                im = Image.open(im_path)
                im.thumbnail((128,128))
                im.save(os.path.join(path, random_name) + "_thumbnail.png", "PNG")

                new_preview = Preview(
                    bind_file_id = new_file.id,
                    url = str(os.path.join(year, month, day , random_name+"_thumbnail.png")).replace('\\', '/')
                )
                db.session.add(new_preview)
                db.session.commit()

            return new_file
            # except:
            #     api.abort(400, "upload failure!")
        else:
            api.abort(400, "file format not allowed!")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower(
           ) in app.config['ALLOWED_EXTENSIONS']