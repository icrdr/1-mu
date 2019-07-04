from flask_restplus import Resource, reqparse
from .. import api, app, db
from ..model import User, WxUser
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
import base64
import requests
import shortuuid
from datetime import datetime, timedelta

n_auth = api.namespace('api/token', description='Authorization Operations')

g_user = reqparse.RequestParser()
g_user.add_argument('Authorization', location='headers')
g_user.add_argument('wxcode', location='args')


@n_auth.route('')
class AuthApi(Resource):
    @api.expect(g_user)
    def get(self):
        args = g_user.parse_args()
        if args['Authorization']:
            auth_data = args['Authorization'].split(" ")[1]
            auth = base64.b64decode(auth_data).decode('utf-8').split(":")
            user = User.query.filter_by(login=auth[0]).first()
            if(user):
                if check_password_hash(user.password, auth[1]):
                    token = jwt.encode({'id': user.id, 'exp': datetime.utcnow(
                    )+timedelta(hours = 24)}, app.config['SECRET_KEY'])
                    return {'token': token.decode('UTF-8')}, 200
                else:
                    return api.abort(400, "wrong password")
            else:
                return api.abort(400, "user not exist")
        elif args['wxcode']:
            url = "https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code" % \
                (app.config['WECHAT_APPID'],
                 app.config['WECHAT_APPSECRET'], args['wxcode'])
            try:
                r = requests.get(url)
                json = r.json()
                if 'access_token' in json:
                    url = "https://api.weixin.qq.com/sns/userinfo?access_token=%s&openid=%s" % \
                        (json['access_token'], json['openid'])
                    try:
                        r = requests.get(url)
                        r.encoding = 'utf-8'
                        json = r.json()
                        if 'openid' in json:
                            wx_user = WxUser.query.filter_by(
                                unionid=json['unionid']).first()
                            if wx_user:
                                wx_user.openid = json['openid'],
                                wx_user.nickname = json['nickname'],
                                wx_user.sex = json['sex'],
                                wx_user.language = json['language'],
                                wx_user.city = json['city'],
                                wx_user.province = json['province'],
                                wx_user.country = json['country'],
                                wx_user.headimg_url = json['headimgurl'],
                                wx_user.unionid = json['unionid']
                            else:
                                new_wx_user = WxUser(
                                    openid=json['openid'],
                                    nickname=json['nickname'],
                                    sex=json['sex'],
                                    language=json['language'],
                                    city=json['city'],
                                    province=json['province'],
                                    country=json['country'],
                                    headimg_url=json['headimgurl'],
                                    unionid=json['unionid']
                                )
                                db.session.add(new_wx_user)
                                new_user = User(
                                    login=str(shortuuid.uuid()),
                                    name=json['nickname'],
                                    password=generate_password_hash(
                                        str(shortuuid.uuid()), method='sha256'),
                                    wx_user=new_wx_user
                                )
                                db.session.add(new_user)
                                wx_user = new_wx_user
                            db.session.commit()
                            token = jwt.encode({'id': wx_user.bind_user_id, 'exp': datetime.utcnow(
                            )+timedelta(hours = 24)}, app.config['SECRET_KEY'])
                            return {
                                'token': token.decode('UTF-8'),
                                'wx_info': json
                            }, 200
                        else:
                            return json, 400
                    except:
                        return api.abort(400, "bad connection")
                else:
                    return json, 400
            except:
                return api.abort(400, "bad connection")
        else:
            return api.abort(400, "bad auth")
