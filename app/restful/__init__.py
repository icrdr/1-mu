# from flask import current_app
from .. import app
PERMISSIONS = app.config['PERMISSIONS']
SECRET_KEY = app.config['SECRET_KEY']

from . import user, post, upload, auth