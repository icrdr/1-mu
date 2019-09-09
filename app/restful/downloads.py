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
import csv
import shortuuid
import zipfile
from ..utility import buildUrl, UTC2Local

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
    .add_argument('mode', location='args', default='compress', choices=['source', 'compress'])\



@N_DOWNLOAD.route('/projects')
class DownloadProjectApi(Resource):
    @permission_required()
    @api.expect(PROJECT_DOWNLOAD)
    def get(self):
        args = PROJECT_DOWNLOAD.parse_args()
        query = Project.query.filter(Project.id.in_(args['project_id']))
        project_list = query.all()

        if project_list:
            if args['mode'] == 'compress':
                task = downloadZipTask.delay(args['project_id'], 'compress')
            elif args['mode'] == 'source':
                task = downloadZipTask.delay(args['project_id'], 'source')

            return {'task_id': task.id}, 202
        else:
            api.abort(400, "file doesn't exist")


PROJECT_TABLE = reqparse.RequestParser()\
    .add_argument('project_id', location='args', required=True, action='split')\
    .add_argument('keys', location='args', required=True, action='split')\
    .add_argument('order', location='args', default='asc', choices=['asc', 'desc'])\
    .add_argument('order_by', location='args', default='id', choices=['id', 'title', 'start_date', 'finish_date', 'status', 'creator_id', 'client_id', 'progress'])


@N_DOWNLOAD.route('/projects/csv')
class DownloadProjectTableApi(Resource):
    @permission_required()
    @api.expect(PROJECT_TABLE)
    def get(self):
        args = PROJECT_TABLE.parse_args()
        project_list = Project.query.filter(
            Project.id.in_(args['project_id'])).all()

        if project_list:
            task = exportTableTask.delay(
                args['project_id'], args['keys'], args['order'], args['order_by'])

            return {'task_id': task.id}, 202
        else:
            api.abort(400, "projects doesn't exist")


def project_query_order(query, order, order_by):
    if order_by == 'id':
        if order == 'asc':
            query = query.order_by(Project.id.asc())
        else:
            query = query.order_by(Project.id.desc())

    elif order_by == 'title':
        if order == 'asc':
            query = query.order_by(Project.title.asc(), Project.id.desc())
        else:
            query = query.order_by(Project.title.desc(), Project.id.desc())

    elif order_by == 'start_date':
        if order == 'asc':
            query = query.order_by(Project.start_date.asc())
        else:
            query = query.order_by(Project.start_date.desc())
    elif order_by == 'finish_date':
        if order == 'asc':
            query = query.order_by(Project.finish_date.asc())
        else:
            query = query.order_by(Project.finish_date.desc())
    elif order_by == 'status':
        if order == 'asc':
            query = query.order_by(Project.status.asc(), Project.id.desc())
        else:
            query = query.order_by(
                Project.status.desc(), Project.id.desc())
    return query


def transfer2Header(keys):
    header = []
    for key in keys:
        if key == 'id':
            header.append('ID')
        elif key == 'title':
            header.append('企划名')
        elif key == 'tags':
            header.append('标签')
        elif key == 'start_date':
            header.append('开始时间')
        elif key == 'finish_date':
            header.append('结束时间')
        elif key == 'deadline_date':
            header.append('死线日期')
        elif key == 'current_stage':
            header.append('目前阶段')
        elif key == 'status':
            header.append('状态')
        elif key == 'progress':
            header.append('进度')
        elif key == 'client':
            header.append('审核者')
        elif key == 'creator':
            header.append('制作者')
    return header


def transfer2Content(keys, project):
    content = []
    for key in keys:
        if key == 'id':
            content.append(project.id)
        elif key == 'title':
            content.append(project.title)
        elif key == 'tags':
            tags = project.tags
            tag_list = []
            for tag in tags:
                tag_list.append(tag.name)
            content.append(';'.join(tag_list))

        elif key == 'start_date':
            if project.start_date:
                content.append(
                    UTC2Local(project.start_date).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                content.append('未开始')
        elif key == 'finish_date':
            if project.finish_date:
                content.append(
                    UTC2Local(project.finish_date).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                content.append('未结束')
        elif key == 'deadline_date':
            deadline_date = project.current_phase().deadline_date
            if deadline_date:
                content.append(
                    UTC2Local(deadline_date).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                content.append('未开始')
        elif key == 'current_stage':
            content.append(project.current_stage().name)
        elif key == 'status':
            status = project.status
            if status == 'draft':
                _str = '草稿'
            elif status == 'await':
                _str = '未开始'
            elif status == 'progress':
                _str = '进行中'
            elif status == 'delay':
                _str = '逾期中'
            elif status == 'pending':
                _str = '待确认'
            elif status == 'abnormal':
                _str = '异常？'
            elif status == 'modify':
                _str = '修改中'
            elif status == 'pause':
                _str = '暂停'
            elif status == 'finish':
                _str = '已完成'
            elif status == 'discard':
                _str = '已废弃'
            else:
                _str = '未知'
            content.append(_str)
        elif key == 'progress':
            status = project.status
            if status == 'finish':
                _str = '完成'
            elif status == 'await' or status == 'draft':
                _str = '未开始'
            elif status == 'abnormal' or status == 'discard':
                _str = '未知'
            else:
                _str = '制作中'
            content.append(_str)
        elif key == 'client':
            content.append(project.client.name)
        elif key == 'creator':
            content.append(project.creator.name)
    print(content)
    return content


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

N_TASK = api.namespace('api/tasks', description='task')
@N_TASK.route('/<string:task_id>')
class TaskApi(Resource):
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
def exportTableTask(self, project_id, keys, order, order_by):
    query = Project.query.filter(Project.id.in_(project_id))
    query = project_query_order(query, order, order_by)
    project_list = query.all()

    if project_list:
        csv_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'temp')
        if not os.path.exists(csv_path):
            os.makedirs(csv_path)
        csv_file = os.path.join(csv_path, str(shortuuid.uuid())+'.csv')

        with open(csv_file, 'w', newline='', encoding="utf-8-sig") as csvfile:
            csvWriter = csv.writer(
                csvfile, dialect='excel', quoting=csv.QUOTE_NONNUMERIC,)
            csvWriter.writerow(transfer2Header(keys))
            for i, project in enumerate(project_list):
                csvWriter.writerow(transfer2Content(keys, project))
                self.update_state(
                    state='PROGRESS',
                    meta={'current': i+1, 'total': len(project_list)}
                )

    return {'current': 100, 'total': 100, 'result': buildUrl(csv_file, dir='')}

@celery.task(bind=True)
def downloadZipTask(self, project_id, mode):
    project_list = Project.query.filter(Project.id.in_(project_id)).all()

    zip_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'temp')
    if not os.path.exists(zip_path):
        os.makedirs(zip_path)
    zip_file = os.path.join(zip_path, str(shortuuid.uuid())+'.zip')
    zipf = zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED)

    for i, project in enumerate(project_list):
        for phase in project.phases:
            if phase.upload_files:
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
