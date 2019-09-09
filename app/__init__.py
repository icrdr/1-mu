from flask import Flask, json
from flask_restplus import Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from celery import Celery
from flask_migrate import Migrate, init as db_init, migrate as db_migrate, upgrade as db_upgrade
from config import config
import os
import redis
from pytz import utc
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta, datetime


app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_ENV')])

# ODM
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# APScheduler
scheduler = BackgroundScheduler()
scheduler.configure(jobstores=app.config['SCHEDULER_JOBSTORES'], timezone=utc)
scheduler.start()

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Redis
r_db = redis.Redis(host='localhost', port=6379, db=0)

# Restful
api = Api(app, doc='/api/doc/', version='1.0',
          title='EMU(一目) API', description='')

# support CORS https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
CORS(app)

from . import view, restful, model
from .utility import word2List

@app.cli.command()
def update():
    # migrate database to latest revision
    db_migrate()
    db_upgrade()

    # update user roles
    model.Role.insert_roles()
    model.File.clear_missing_file()


@app.cli.command()
def init():
    # create tables
    db.create_all()

    # create user roles
    model.Role.insert_roles()
    model.User.create_admin()
    model.Option.init_option()
    db_init()


@app.cli.command()
def dropProject():
    model.Project.delete_all_project()

        
@app.cli.command()
def fixCreator():
    projects = model.Project.query.all()
    for project in projects:
        print(project.id)
        if project.creator_group:
            project.creator_user_id = project.creator_group.admins[0].id
            for phase in project.phases:
                if phase.creator_user_id:
                    project.creator_user_id = phase.creator_user_id
        print(project.creator)
        db.session.commit()

@app.cli.command()
def fixStage():
    phases = model.Phase.query.all()
    for phase in phases:
        phase.project_id = phase.parent_project_id
        phase.stage_id = phase.parent_stage_id

    stages = model.Stage.query.all()
    for stage in stages:
        stage.project_id = stage.parent_project_id
        stage.days_planned = stage.days_need
    
    projects = model.Project.query.all()
    for project in projects:
        if project.status =='await':
            project.progress = 0
            project.start_date == None
            project.finish_date == None
        elif project.status =='finish':
            project.progress = -1
        else:
            project.finish_date == None
            project.progress = project.current_stage_index+1
    db.session.commit()

@app.cli.command()
def fixbool2():
    files = model.File.query.all()
    for file in files:
        if not file.public:
            file.public = False
    projects = model.Project.query.all()
    for project in projects:
        if not project.public:
            project.public = False
    db.session.commit()

@app.cli.command()
def fixbool():
    projects = model.Project.query.all()
    for project in projects:
        if project.status == 'pause' or project.status == 'discard':
            if project.current_phase():
                if project.current_phase().feedback_date:
                    project.status = 'finish'
                elif project.current_phase().upload_date:
                    project.status = 'pending'
                elif project.current_phase().start_date:
                    if len(project.current_stage().phases) > 1:
                        project.status = 'modify'
                    else:
                        project.status = 'progress'
                else:
                    project.status = 'await'
            else:
                project.status = 'await'
                
            if project.status == 'pause':
                project.pause = True

            if project.status == 'discard':
                project.discard = True
        else:
            project.discard = False
            project.pause = False

        if project.status == 'delay':
            if len(project.current_stage().phases) > 1:
                project.status = 'modify'
            else:
                project.status = 'progress'
            project.delay = True
        else:
            project.delay = False
        current_phase = project.current_phase()
        if current_phase:
            project.deadline_date = current_phase.deadline_date
        db.session.commit()

@app.cli.command()
def fixTX():
    _tag = model.Tag.query.filter_by(name='腾讯医典词条').first()
    if not _tag:
        _tag = model.Tag(name='腾讯医典词条')
        db.session.add(_tag)
        db.session.commit()
    
    projects = model.Project.query.all()
    for project in projects:
        print(project.id)
        isOK = True
        for tag in project.tags:
            if tag.name == '样图' or tag.name == '腾讯医典词条':
                isOK = False
        if isOK:
            project.tags.append(_tag)
            db.session.commit()

@app.cli.command()
def fixTag():
    files = model.File.query.all()
    for file in files:
        if len(file.tags)>0:
            print(file.id)
            new_tags = []
            for tag in file.tags:
                taglist = word2List(tag.name)
                if len(taglist)>1:
                    for _t in taglist:
                        _tag = model.Tag.query.filter_by(name=_t).first()
                        if not _tag:
                            _tag = model.Tag(name=_t)
                            db.session.add(_tag)
                        new_tags.append(_tag)
                    db.session.delete(tag)
                else:
                    new_tags.append(tag)
            file.tags = []
            for n_tag in new_tags:
                file.tags.append(n_tag)
            db.session.commit()

    projects = model.Project.query.all()
    for project in projects:
        if len(project.tags)>0:
            print(project.id)
            new_tags = []
            for tag in project.tags:
                taglist = word2List(tag.name)
                if len(taglist)>1:
                    for _t in taglist:
                        _tag = model.Tag.query.filter_by(name=_t).first()
                        if not _tag:
                            _tag = model.Tag(name=_t)
                            db.session.add(_tag)
                        new_tags.append(_tag)
                    db.session.delete(tag)
                else:
                    new_tags.append(tag)
            project.tags = []
            for n_tag in new_tags:
                project.tags.append(n_tag)
            db.session.commit()
    none_tag = model.Tag.query.filter_by(name='').first()
    if none_tag:
        db.session.delete(none_tag)
        db.session.commit()

@app.cli.command()
def doc():
    with app.app_context(), app.test_request_context():
        urlvars = False  # Build query strings in URLs
        swagger = True  # Export Swagger specifications
        data = api.as_postman(urlvars=urlvars, swagger=swagger)
        with open("api.json", 'w') as file:  # Use file to refer to the file object
            print(json.dumps(data))
            file.write(json.dumps(data))
