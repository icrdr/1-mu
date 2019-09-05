from . import app
import os
from datetime import datetime
from dateutil import tz
import re

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

def UTC2Local(date):
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()

    date = date.replace(tzinfo=from_zone)

    # Convert time zone
    local = date.astimezone(to_zone)
    return local
def getStageIndex(stage):
    project = stage.parent_project
    index = 0
    for i, s in enumerate(project.stages):
        if s.id == stage.id:
            index =i
    return index

def getPhaseIndex(phase):
    stage = phase.parent_stage
    index = 0
    for i, p in enumerate(stage.phases):
        if p.id == phase.id:
            index =i
    return index
def excerptHtml(html,length=20):
    pattern = re.compile(r'<[^>]+>',re.S)
    result = pattern.sub('', html)
    if len(result)>20:
        result = result[:length]+'...'
    return result

def word2List(string):
    return re.findall(r"[\w']+", string)