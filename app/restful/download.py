from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db, app
from ..model import File, PERMISSIONS

from werkzeug import utils, datastructures
from .decorator import permission_required, admin_required
from datetime import datetime
import os, shortuuid, zipfile
from ..utility import buildUrl

n_download = api.namespace('api/download', description='upload operations')

m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'description': fields.String(description="The title for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
    'format': fields.String(description="Registration date for the user."),
})

g_download = reqparse.RequestParser()
g_download.add_argument('file_id', location='args', required=True, action='split',
                    help="Limit result set to users matching at least one specific \
                    role provided. Accepts list or single role.")

@n_download.route('')
class DownloadApi(Resource):
    @permission_required()
    @api.expect(g_download)
    def get(self):
        args = g_download.parse_args()
        files_list = File.query.filter(File.id.in_(args['file_id'])).all()
        if files_list:
            try:
                zip_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'temp')
                if not os.path.exists(zip_path):
                    os.makedirs(zip_path)
                zip_file = os.path.join(zip_path, str(shortuuid.uuid())+'.zip')
                zipf = zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED)

                for file in files_list:
                    filename = file.name+'.'+file.format
                    zipf.write(os.path.join(app.config['UPLOAD_FOLDER'], file.url), filename)

                zipf.close()
                return {'download_url': buildUrl(zip_file, dir='')}, 200
            except Exception as e:
                print(e)
                api.abort(400, "zip failure")
        else:
            api.abort(400, "file doesn't exist")