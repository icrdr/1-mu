from flask import Flask, json
from flask_restplus import Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate, init as db_init, migrate as db_migrate, upgrade as db_upgrade
from config import config
import os
import redis
from pytz import utc
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta
app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_ENV')])

# ODM
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# APScheduler
scheduler = BackgroundScheduler()
scheduler.configure(jobstores=app.config['SCHEDULER_JOBSTORES'], timezone=utc)
scheduler.start()

# Redis
r_db = redis.Redis(host='localhost', port=6379, db=0)

# Restful
api = Api(app, doc='/api/doc/', version='1.0',
          title='EMU(一目) API', description='')

# support CORS https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
CORS(app)

from . import view, restful, model

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
def fixProject():
    phases = model.Phase.query.all()
    for phase in phases:
        print(phase.id)
        if not phase.parent_project_id:
            phase.parent_project_id = phase.parent_stage.parent_project_id
        stage = phase.parent_stage
        if stage.start_date:
            if stage.phases.index(phase) == 0:
                phase_start_date = stage.start_date
            else:
                index = stage.phases.index(phase) - 1
                phase_start_date = stage.phases[index].feedback_date
            phase.start_date = phase_start_date
            phase.deadline_date = phase_start_date + timedelta(days=phase.days_need)

        db.session.commit()
        
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
def fixTag():
    files = model.File.query.all()
    for file in files:
        if len(file.tags)>0:
            print(file.id)
            new_tags = []
            for tag in file.tags:
                taglist = tag.name.split(',')
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

@app.cli.command()
def doc():
    with app.app_context(), app.test_request_context():
        urlvars = False  # Build query strings in URLs
        swagger = True  # Export Swagger specifications
        data = api.as_postman(urlvars=urlvars, swagger=swagger)
        with open("api.json", 'w') as file:  # Use file to refer to the file object
            print(json.dumps(data))
            file.write(json.dumps(data))
