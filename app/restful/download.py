from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db, app
from ..model import File, Project

from werkzeug import utils, datastructures
from .decorator import permission_required, admin_required
from datetime import datetime
import os
import shortuuid
import zipfile
from ..utility import buildUrl
PERMISSIONS = app.config['PERMISSIONS']
n_download = api.namespace('api/download', description='upload operations')

m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'description': fields.String(description="The title for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url), description="The avatar url for the user."),
    'format': fields.String(description="Registration date for the user."),
})

FILE_DOWNLOAD = reqparse.RequestParser()
FILE_DOWNLOAD.add_argument('file_id', location='args',
                           required=True, action='split')


@n_download.route('/files')
class DownloadApi(Resource):
    @permission_required()
    @api.expect(FILE_DOWNLOAD)
    def get(self):
        args = FILE_DOWNLOAD.parse_args()
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
                    zipf.write(os.path.join(
                        app.config['UPLOAD_FOLDER'], file.url), filename)

                zipf.close()
                return {'download_url': buildUrl(zip_file, dir='')}, 200
            except Exception as e:
                print(e)
                api.abort(400, "zip failure")
        else:
            api.abort(400, "file doesn't exist")


PROJECT_DOWNLOAD = reqparse.RequestParser()
PROJECT_DOWNLOAD.add_argument(
    'project_id', location='args', required=True, action='split')


@n_download.route('/projects')
class DownloadProjectApi(Resource):
    @permission_required()
    @api.expect(PROJECT_DOWNLOAD)
    def get(self):
        args = PROJECT_DOWNLOAD.parse_args()
        project_list = Project.query.filter(
            Project.id.in_(args['project_id'])).all()
        if project_list:
            try:
                zip_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'temp')
                if not os.path.exists(zip_path):
                    os.makedirs(zip_path)
                zip_file = os.path.join(zip_path, str(shortuuid.uuid())+'.zip')
                zipf = zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED)

                for project in project_list:
                    phase = project.current_phase()

                    last_upload_phase = None

                    for phase in project.phases:
                        if len(phase.upload_files) > 0:
                            last_upload_phase = phase

                    if last_upload_phase:
                        foldername = project.title
                        if project.status == 'finish':
                            foldername = '{} {}'.format(project.title, '完成')
                        else:
                            foldername = '{} {}'.format(project.title, project.current_stage().name)
                        for upload_file in last_upload_phase.upload_files:
                            filename = upload_file.name+'.'+upload_file.format
                            zipf.write(
                                os.path.join(
                                    app.config['UPLOAD_FOLDER'],
                                    upload_file.url
                                ),
                                os.path.join(foldername, filename)
                            )

                zipf.close()
                return {'download_url': buildUrl(zip_file, dir='')}, 200
            except Exception as e:
                print(e)
                api.abort(400, "zip failure")
        else:
            api.abort(400, "file doesn't exist")
