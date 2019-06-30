from flask import Flask, send_from_directory
from flask_restplus import Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object('config')

# ODM
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# restful
api = Api(app, doc='/doc/', version='1.0', title='EMU(一目) API',
    description='')

# support CORS https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
CORS(app)

from . import view, restful, model