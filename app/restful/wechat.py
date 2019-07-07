from flask_restplus import Resource, reqparse
from .. import api, app, db, scheduler
from ..model import User, WxUser, Option
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
import json
import requests
import shortuuid
import urllib
from datetime import datetime, timedelta

n_wechat = api.namespace('api/wechat', description='Authorization Operations')

g_user = reqparse.RequestParser()
g_user.add_argument('wxcode', required=True, location='args')
g_user.add_argument('wxtype', required=True, location='args')


@n_wechat.route('/auth')
class WxAuthApi(Resource):
    @api.expect(g_user)
    def get(self):
        args = g_user.parse_args()
        # step 1: get access code from client.
        url = 'https://api.weixin.qq.com/sns/oauth2/access_token'
        appid = secret = ''
        
        if args['wxtype'] == 'gz':
            appid = app.config['WECHAT_GZ_APPID']
            secret = app.config['WECHAT_GZ_APPSECRET']
        elif args['wxtype'] == 'kf':
            appid = app.config['WECHAT_KF_APPID']
            secret = app.config['WECHAT_KF_APPSECRET']

        params = {
            "grant_type": "authorization_code",
            "appid": appid,
            "secret": secret,
            "code": args['wxcode']
        }
        print(params)
        try:  # step 2: get access_token from wechat serves.
            # data = requests.get(url, params=payload).json()
            r = requests.get(url, params=params)
            data=r.json()
            print(r.url)
            if 'access_token' in data:
                url = "https://api.weixin.qq.com/sns/userinfo"
                params = {
                    "access_token": data['access_token'],
                    "openid": data['openid'],
                }
                try:  # step 3: get userinfo with access_token from wechat serves.
                    res = requests.get(url, params=params)
                    res.encoding = 'utf-8'
                    data = res.json()
                    if 'openid' in data:
                        wx_user = WxUser.query.filter_by(
                            unionid=data['unionid']).first()
                        # check if the wechat unionid is already registed on our serves
                        if wx_user:  # if so, update his info
                            wx_user.openid = data['openid'],
                            wx_user.nickname = data['nickname'],
                            wx_user.sex = data['sex'],
                            wx_user.language = data['language'],
                            wx_user.city = data['city'],
                            wx_user.province = data['province'],
                            wx_user.country = data['country'],
                            wx_user.headimg_url = data['headimgurl'],
                            wx_user.unionid = data['unionid']
                        else:  # otherwise, create a new one
                            new_wx_user = WxUser(
                                openid=data['openid'],
                                nickname=data['nickname'],
                                sex=data['sex'],
                                language=data['language'],
                                city=data['city'],
                                province=data['province'],
                                country=data['country'],
                                headimg_url=data['headimgurl'],
                                unionid=data['unionid']
                            )
                            db.session.add(new_wx_user)

                            # create a new account on our serves and bind it to the wechat account.
                            new_user = User(
                                login=str(shortuuid.uuid()),
                                name=data['nickname'],
                                password=generate_password_hash(
                                    str(shortuuid.uuid()), method='sha256'),
                                wx_user=new_wx_user
                            )
                            db.session.add(new_user)
                            wx_user = new_wx_user

                        db.session.commit()
                        # generate a jwt based on user id
                        token = jwt.encode({'id': wx_user.bind_user_id, 'exp': datetime.utcnow(
                        )+timedelta(hours=24)}, app.config['SECRET_KEY'])
                        return {
                            'token': token.decode('UTF-8'),
                            'wx_info': data
                        }, 200
                    else:
                        return data, 400
                except Exception as e:
                    print(e)
                    return api.abort(400, "bad connection")
            else:
                return data, 400
        except Exception as e:
            print(e)
            return api.abort(400, "bad connection")


@n_wechat.route('/token')
class WxTokenApi(Resource):
    def post(self):
        try:
            scheduler.delete_job('update_wechat_access_token')
        except Exception as e:
            print(e)

        scheduler.add_job(
            id='update_wechat_access_token',
            func=getAccessToken,
            trigger='interval',
            minutes=110
        )
        return getAccessToken()


@n_wechat.route('/qrcode')
class WxQrcodeApi(Resource):
    def get(self):
        option = Option.query.filter_by(name='wechat_access_token').first()
        url = 'https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token=%s' % option.value
        data = {
            "expire_seconds": 604800,
            "action_name": "QR_SCENE",
            "action_info": {
                "scene": {"scene_id": 123}
            }
        }
        try:
            # json.dumps for json format. Otherwise, wechat will return error.
            data = requests.post(url, data=json.dumps(data)).json()
            if 'ticket' in data:
                return {'ticket':data['ticket']},200
            else:
                return data, 400
        except Exception as e:
            print(e)
            return api.abort(400, "bad connection")


def getAccessToken():
    url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s' % (
        app.config['WECHAT_GZ_APPID'],
        app.config['WECHAT_GZ_APPSECRET']
    )
    try:
        data = requests.get(url).json()
        if 'access_token' in data:
            print(data['access_token'])
            option = Option.query.filter_by(name='wechat_access_token').first()
            if option:
                option.value = data['access_token']
            else:
                new_option = Option(
                    name='wechat_access_token',
                    value=data['access_token']
                )
                db.session.add(new_option)
            db.session.commit()
            return data, 200
        else:
            return data, 400

    except Exception as e:
        print(e)
        return api.abort(400, "bad connection")
