from flask import request
from urllib.parse import urlparse, urlunparse
from .. import app

def buildUrl(path):
    url_parts = list(urlparse(request.host_url))
    url_parts[2] += app.config['UPLOAD_FOLDER'] + path
    return urlunparse(url_parts)

from . import user, post, auth, upload