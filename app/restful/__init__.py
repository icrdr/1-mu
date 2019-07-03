from flask import request
from urllib.parse import urlparse, urlunparse
from .. import app

def buildUrl(path, dir=app.config['UPLOAD_FOLDER']):
    url_parts = list(urlparse(request.host_url))
    url_parts[2] += dir + path
    return urlunparse(url_parts).replace('\\', '/')

from . import user, post, auth, file, download, project