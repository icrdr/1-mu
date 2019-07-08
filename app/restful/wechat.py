from flask import request, Response
import hashlib
from flask_restplus import Resource, reqparse
from .. import api, app, db, scheduler, r_db
from ..model import User, WxUser, Option
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
import json
import requests
import shortuuid
import urllib
import xmltodict
import time
from datetime import datetime, timedelta

n_wechat = api.namespace('api/wechat', description='Authorization Operations')


g_wx = reqparse.RequestParser()
g_wx.add_argument('signature', required=True, location='args')
g_wx.add_argument('timestamp', required=True, location='args')
g_wx.add_argument('nonce', required=True, location='args')
g_wx.add_argument('echostr', location='args')


@n_wechat.route('')
class WxApi(Resource):
    def get(self):
        args = g_wx.parse_args()
        echostr = request.args.get("echostr")
        li = ['yixuechahua', args['timestamp'], args['nonce']]

        li.sort()
        # 拼接字符串 不编码的话python会报错
        tmp_str = "".join(li).encode('utf-8')
        # 进行sha1加密
        sign = hashlib.sha1(tmp_str).hexdigest()
        # 将自己的签名与微信进行对比
        if args['signature'] == sign:
            print('yes!')
            # 如果签名与微信的一致需返回echostr给微信
            return int(args['echostr']), 200
        else:
            print('no!')
            return api.abort(403, "sign not right")

    def post(self):
        # xml can't parse by the RequestParser, so we have to use the flask request.data
        xml_str = request.data

        if not xml_str:
            return api.abort(403, "nothing get")
        # 对xml字符串进行解析
        xml_dict = xmltodict.parse(xml_str, encoding='utf-8')
        xml_dict = xml_dict['xml']
        print(xml_dict['MsgType'])
        if(xml_dict['MsgType'] == 'event'):

            print(xml_dict['EventKey'])
            print(xml_dict['FromUserName'])
            if 'login' in xml_dict['EventKey']:
                try:
                    r_db.set(xml_dict['EventKey'], xml_dict['FromUserName'])
                except Exception as e:
                    print(e)

            return Response('')

        elif(xml_dict['MsgType'] == 'text'):
            # 提取消息类型
            # msg_type = xml_dict.get("MsgType")
            resp_dict = {
                "xml": {
                    "ToUserName": xml_dict['FromUserName'],
                    "FromUserName": xml_dict['ToUserName'],
                    "CreateTime": int(time.time()),
                    "MsgType": "news",
                    "ArticleCount": 1,
                    "Articles": {
                        "item": {
                            "Title": '标题',
                            "Description": "描述",
                            "PicUrl": "http://www.1-mu.net/upload/2019/07/08/rMeLwGCWrArb2FaPcTBoqJ_256.png",
                            "Url": 'http://beta.1-mu.net/'
                        }
                    }
                }
            }

            # 将字典转换为xml字符串
            resp_xml_str = xmltodict.unparse(resp_dict, encoding='utf-8')
            # 返回消息数据给微信服务器
            return Response(resp_xml_str, mimetype='text/xml')
            # return Response('')


g_user = reqparse.RequestParser()
g_user.add_argument('wxcode', required=True, location='args')
# g_user.add_argument('wxtype', required=True, location='args')


@n_wechat.route('/auth')
class WxAuthApi(Resource):
    @api.expect(g_user)
    def get(self):
        args = g_user.parse_args()
        # step 1: get access code from client.
        url = 'https://api.weixin.qq.com/sns/oauth2/access_token'

        # appid = secret = ''

        # if args['wxtype'] == 'gz':
        #     appid = app.config['WECHAT_GZ_APPID']
        #     secret = app.config['WECHAT_GZ_APPSECRET']
        # elif args['wxtype'] == 'kf':
        #     appid = app.config['WECHAT_KF_APPID']
        #     secret = app.config['WECHAT_KF_APPSECRET']

        params = {
            "grant_type": "authorization_code",
            "appid": app.config['WECHAT_GZ_APPID'],
            "secret": app.config['WECHAT_GZ_APPSECRET'],
            "code": args['wxcode']
        }

        try:  # step 2: get access_token from wechat serves.
            # data = requests.get(url, params=payload).json()
            data = requests.get(url, params=params).json()
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
                    if 'unionid' in data:
                        return createUser(data)
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


g_check = reqparse.RequestParser()
g_check.add_argument('scene_str', location='args')
@n_wechat.route('/check')
class WxLoginApi(Resource):
    def get(self):
        args = g_check.parse_args()
        openid = r_db.get(args['scene_str']).decode('UTF-8')
        # print(openid)
        if openid != 'None':
            option = Option.query.filter_by(name='wechat_access_token').first()
            url = "https://api.weixin.qq.com/cgi-bin/user/info"
            params = {
                "access_token": option.value,
                "openid": openid,
            }
            try:
                res = requests.get(url, params=params)
                res.encoding = 'utf-8'
                data = res.json()
                if 'unionid' in data:
                    return createUser(data)
                else:
                    return data, 400

            except Exception as e:
                print(e)
                return api.abort(400, "bad connection")
        else:
            return api.abort(400, "not yet!")


@n_wechat.route('/menu')
class WxMenuApi(Resource):
    def post(self):
        option = Option.query.filter_by(name='wechat_access_token').first()
        url = "https://api.weixin.qq.com/cgi-bin/menu/create"
        params = {
            "access_token": option.value,
        }
        data = {
            "button": [
                {
                    "name": "一目学堂",
                    "sub_button": [
                        {
                            "type": "view_limited",
                            "name": "医学数字插画",
                            "media_id": "F8EWugFQrW6deUZOeUy9arpbtH8fQOqmBE4q_DHF3rc"
                        },
                        {
                            "type": "view_limited",
                            "name": "3D培训",
                            "media_id": "F8EWugFQrW6deUZOeUy9atscsZY9vpmVyQD838Ir9FY"
                        },
                        {
                            "type": "view_limited",
                            "name": "PPT培训",
                            "media_id": "F8EWugFQrW6deUZOeUy9anBxSlYBXC7Y0QbD466YAPY"
                        }
                    ]
                },
                {
                 "type": "miniprogram",
                 "name": "一目社区",
                 "url": "http://www.1-mu.net",
                 "appid": "wx9c6611278d5fe9cf",
                 "pagepath": "pages/index/index"
                },
                {
                    "name": "一目创造",
                    "sub_button": [
                        {
                            "type": "view_limited",
                            "name": "关于我们",
                            "media_id": "F8EWugFQrW6deUZOeUy9avhRYOffX2gcSJFflevky80"
                        }
                    ]
                }
            ]
        }
        try:
            print(json.dumps(data).encode('utf-8'))
            print(json.dumps(data, ensure_ascii=False))
            res= requests.post(url, params=params, data=json.dumps(data, ensure_ascii=False).encode('utf-8'))
            data= res.json()
            return data, 200

        except Exception as e:
            print(e)
            return api.abort(400, "bad connection")


@n_wechat.route('/qrcode')
class WxQrcodeApi(Resource):
    def get(self):
        scene_str= 'login'+str(shortuuid.uuid())
        option= Option.query.filter_by(name='wechat_access_token').first()
        url= 'https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token=%s' % option.value
        data= {
            "expire_seconds": 604800,
            "action_name": "QR_STR_SCENE",
            "action_info": {
                "scene": {"scene_str": scene_str}
            }
        }
        r_db.set(scene_str, 'None')
        try:
            # json.dumps for json format. Otherwise, wechat will return error.
            data= requests.post(url, data=json.dumps(data)).json()
            if 'ticket' in data:
                return {'ticket': data['ticket'], 'scene_str': scene_str}, 200
            else:
                return data, 400
        except Exception as e:
            print(e)
            return api.abort(400, "bad connection")


def getAccessToken():
    url= 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s' % (
        app.config['WECHAT_GZ_APPID'],
        app.config['WECHAT_GZ_APPSECRET']
    )
    try:
        data= requests.get(url).json()
        if 'access_token' in data:
            print(data['access_token'])
            option= Option.query.filter_by(name='wechat_access_token').first()
            if option:
                option.value= data['access_token']
            else:
                new_option= Option(
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


def createUser(data):
    try:
        wx_user= WxUser.query.filter_by(unionid=data['unionid']).first()
        # check if the wechat unionid is already registed on our serves
        if wx_user:  # if so, update his info
            wx_user.openid= data['openid'],
            wx_user.nickname= data['nickname'],
            wx_user.sex= data['sex'],
            wx_user.language= data['language'],
            wx_user.city= data['city'],
            wx_user.province= data['province'],
            wx_user.country= data['country'],
            wx_user.headimg_url= data['headimgurl'],
            wx_user.unionid= data['unionid']
        else:  # otherwise, create a new one
            new_wx_user= WxUser(
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
            new_user= User(
                login=str(shortuuid.uuid()),
                name=data['nickname'],
                password=generate_password_hash(
                    str(shortuuid.uuid()), method='sha256'),
                wx_user=new_wx_user
            )
            db.session.add(new_user)
            wx_user= new_wx_user

        db.session.commit()
        # generate a jwt based on user id
        token= jwt.encode({'id': wx_user.bind_user_id, 'exp': datetime.utcnow(
        )+timedelta(hours=24)}, app.config['SECRET_KEY'])
        return {
            'token': token.decode('UTF-8'),
            'wx_info': data
        }, 200
    except Exception as e:
        print(e)
        return api.abort(400, "create user failed")
