from . import app
import os
from datetime import datetime
from dateutil import tz
import re
import time
import hashlib
import shortuuid


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
    if project:
        for i, s in enumerate(project.stages):
            if s.id == stage.id:
                index = i
    return index


def getPhaseIndex(phase):
    stage = phase.parent_stage
    print(phase)
    print(stage)
    index = 0
    if stage:
        for i, p in enumerate(stage.phases):
            if p.id == phase.id:
                index = i
    return index


def excerptHtml(html, length=20):
    pattern = re.compile(r'<[^>]+>', re.S)
    result = pattern.sub('', html)
    if len(result) > 20:
        result = result[:length]+'...'
    return result


def word2List(string):
    return re.findall(r"[\w']+", string)


def md5sum(src):
    m = hashlib.md5()
    m.update(src.encode("utf-8"))
    return m.hexdigest()


def getAuthKey(appName, streamName, key, exp):
    path = "/%s/%s" % (appName, streamName)
    rand = "0"
    uid = "0"
    sstring = "%s-%s-%s-%s-%s" % (path, exp, rand, uid, key)
    hashvalue = md5sum(sstring)
    return "%s-%s-%s-%s" % (exp, rand, uid, hashvalue)


def generatePushUrl(streamName):
    host = app.config['LIVE_PUSH_HOST']
    appName = app.config['LIVE_APP_NAME']
    key = app.config['PUSH_KEY']
    exp = int(time.time()) + 6 * 3600
    auth_key = getAuthKey(appName, streamName, key, exp)
    url = "rtmp://{}/{}".format(host, appName)
    auth = "{}?auth_key={}".format(streamName, auth_key)
    return url, auth


def generatePullUrl(streamName):
    host = app.config['LIVE_PULL_HOST']
    appName = app.config['LIVE_APP_NAME']
    key = app.config['PULL_KEY']
    exp = int(time.time()) + 6 * 3600
    auth_key = getAuthKey(appName, streamName, key, exp)
    auth_key_flv = getAuthKey(appName, streamName+'.flv', key, exp)
    auth_key_hls = getAuthKey(appName, streamName+'.m3u8', key, exp)
    rtmp_url = "rtmp://{}/{}/{}?auth_key={}".format(
        host, appName, streamName, auth_key)
    flv_url = "http://{}/{}/{}.flv?auth_key={}".format(
        host, appName, streamName, auth_key_flv)
    hls_url = "http://{}/{}/{}.m3u8?auth_key={}".format(
        host, appName, streamName, auth_key_hls)
    return rtmp_url, flv_url, hls_url
