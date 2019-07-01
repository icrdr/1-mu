# from flask import current_app
from .. import app
SECRET_KEY = app.config['SECRET_KEY']

from . import user, post, upload, auth