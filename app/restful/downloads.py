from flask_restplus import Resource, reqparse, fields
from flask import g, request
from .. import api, db, app, celery
from celery.result import AsyncResult
from ..model import File, Project
from werkzeug import utils, datastructures
from .decorator import permission_required, admin_required
from datetime import datetime
from psd_tools import PSDImage
from PIL import Image
import time
import os
import shortuuid
import zipfile
from ..utility import buildUrl

PERMISSIONS = app.config['PERMISSIONS']
N_DOWNLOAD = api.namespace('api/download', description='upload operations')

m_file = api.model('file', {
    'id': fields.Integer(description="Unique identifier for the user."),
    'name': fields.String(description="Display name for the user."),
    'description': fields.String(description="The title for the user."),
    'url': fields.String(attribute=lambda x: buildUrl(x.url)),
    'format': fields.String(description="Registration date for the user."),
})

FILE_DOWNLOAD = reqparse.RequestParser()
FILE_DOWNLOAD.add_argument('file_id', location='args',
                           required=True, action='split')


@N_DOWNLOAD.route('/files')
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


PROJECT_DOWNLOAD = reqparse.RequestParser()\
    .add_argument('project_id', location='args', required=True, action='split')\
    .add_argument('mode', location='args', default='compress', choices=['source', 'compress'])


@N_DOWNLOAD.route('/projects')
class DownloadProjectApi(Resource):
    @permission_required()
    @api.expect(PROJECT_DOWNLOAD)
    def get(self):
        args = PROJECT_DOWNLOAD.parse_args()
        project_list = Project.query.filter(
            Project.id.in_(args['project_id'])).all()

        if project_list:
            if args['mode'] == 'compress':
                task = zipTask.delay(args['project_id'], 'compress')
            elif args['mode'] == 'source':
                task = zipTask.delay(args['project_id'], 'source')

            return {'task_id': task.id}, 202
        else:
            api.abort(400, "file doesn't exist")


M_RESULT = api.model('result', {
    'current': fields.Integer(),
    'total': fields.Integer(),
    'result': fields.String(),
})

M_TASK = api.model('task', {
    'id': fields.String(),
    'state': fields.String(),
    'result': fields.Nested(M_RESULT),
})


@N_DOWNLOAD.route('/zip/<string:task_id>')
class ZipTaskApi(Resource):
    @api.marshal_with(M_TASK)
    @permission_required()
    def get(self, task_id):
        print(task_id)
        task = celery.AsyncResult(task_id)
        if task:
            return task, 200
        else:
            api.abort(400, "task doesn't exist")


@celery.task(bind=True)
def zipTask(self, project_id_list, mode):
    project_list = Project.query.filter(Project.id.in_(project_id_list)).all()

    zip_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'temp')
    if not os.path.exists(zip_path):
        os.makedirs(zip_path)
    zip_file = os.path.join(zip_path, str(shortuuid.uuid())+'.zip')
    zipf = zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED)

    for i, project in enumerate(project_list):
        phase = project.current_phase()

        last_upload_phase = None

        for phase in project.phases:
            if len(phase.upload_files) > 0:
                last_upload_phase = phase

        if last_upload_phase:
            foldername = project.title
            if project.status != 'finish':
                foldername = '{}-{}'.format(project.title,
                                            project.current_stage().name)

            for j, upload_file in enumerate(last_upload_phase.upload_files):
                index_number = '{:03}'.format(j)

                # compress
                if mode == 'compress' and upload_file.format in ['png', 'psd', 'bmp', 'tga', 'tiff', 'tif']:
                    try:
                        im_path = os.path.join(
                            app.config['UPLOAD_FOLDER'], upload_file.url)
                        if upload_file.format == 'psd':
                            psd = PSDImage.open(im_path)
                            im = psd.compose()
                        else:
                            im = Image.open(im_path)
                        im = im.convert('RGB')
                        filename = '{}.{}.{}'.format(
                            project.title, index_number, 'jpg')
                        im.save(os.path.join(zip_path, filename), "JPEG")
                        zipf.write(
                            os.path.join(zip_path, filename),
                            os.path.join(foldername, filename)
                        )
                    except Exception as e:
                        print(e)
                else:
                    filename = '{}.{}.{}'.format(
                        project.title, index_number, upload_file.format)
                    zipf.write(
                        os.path.join(
                            app.config['UPLOAD_FOLDER'], upload_file.url),
                        os.path.join(foldername, filename)
                    )

        self.update_state(
            state='PROGRESS',
            meta={'current': i+1, 'total': len(project_list)}
        )

    zipf.close()
    return {'current': 100, 'total': 100, 'result': buildUrl(zip_file, dir='')}
