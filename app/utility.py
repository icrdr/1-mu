from . import app
import os
def buildUrl(path, dir=app.config['UPLOAD_FOLDER']):
    if path:
        return str(os.path.join(app.config['DOMAIN_URL'], dir + path)).replace('\\', '/')
    else:
        return ''
    