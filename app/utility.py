from . import app
import os
def buildUrl(path, dir=app.config['UPLOAD_FOLDER']):
    if path:
        return str(os.path.join(app.config['DOMAIN_URL'], dir + path)).replace('\\', '/')
    else:
        return ''
    
def getAvatar(user):
    try:
        if user.wx_user:
            return user.wx_user.headimg_url
        elif user.avatar:
            return user.avatar.url
        else:
            return ''
    except Exception as e:
        print(e)