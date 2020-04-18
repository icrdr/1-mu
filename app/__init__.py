from flask import Flask, json
from flask_restplus import Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
# from flask_socketio import SocketIO, send
from celery import Celery
from flask_migrate import Migrate, init as db_init, migrate as db_migrate, upgrade as db_upgrade
from config import config
import os
import redis
from pytz import utc
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta, datetime
from pathlib import Path

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
def doc():
    with app.app_context(), app.test_request_context():
        urlvars = False  # Build query strings in URLs
        swagger = True  # Export Swagger specifications
        data = api.as_postman(urlvars=urlvars, swagger=swagger)
        with open("api.json", 'w') as file:  # Use file to refer to the file object
            print(json.dumps(data))
            file.write(json.dumps(data))

@app.cli.command()
def psds():
    files = model.File.query.filter(model.File.format.in_(['psd','tif'])).all()
    end = datetime(2021, 1, 1)
    for file in files:
        if len(file.previews) > 0 and file.phases_as_upload:
            need_delete = True
            tags = file.phases_as_upload[0].project.tags
            for tag in tags:
                if tag.name == '样图':
                    need_delete = False 
            if file.upload_date > end:
                need_delete = False
            if need_delete:
                print(file.id)
                print(file.url)
                path = app.config['UPLOAD_FOLDER'] / Path(file.url)
                if path.exists():
                    print('ok')
                    path.unlink()
                break
            # psd.url = psd.previews[0].url
            # psd.format = 'jpg'
            # db.session.commit()

            # path = app.config['UPLOAD_FOLDER'] / Path(psd.url)
            # if path.exists():
            #     path.unlink()

# @app.cli.command()
# def tags():
#     projects = model.Project.query.join(model.Project.tags).filter(
#         model.Tag.name.in_(['腾讯军医词条', '腾讯医典词条'])).all()
#     Tag1 = model.Tag.query.filter(model.Tag.name == '腾讯军医词条').first()
#     Tag2 = model.Tag.query.filter(model.Tag.name == '腾讯医典词条').first()
#     Tag3 = model.Tag.query.filter(model.Tag.name == '腾讯综述').first()
#     for project in projects:
#         print(project.id)
#         project.tags.append(Tag3)
#         if Tag1 in project.tags:
#             project.tags.remove(Tag1)
#         if Tag2 in project.tags:
#             project.tags.remove(Tag2)
#         db.session.commit()
