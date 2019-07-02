from flask import Flask
from flask_restplus import Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate, init as db_init, migrate as db_migrate, upgrade as db_upgrade
from config import config
import os

app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_ENV')])

# ODM
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# restful
api = Api(app, doc='/api/doc/', version='1.0', title='EMU(一目) API', description='')

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
    db_init()
