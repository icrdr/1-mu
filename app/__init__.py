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
