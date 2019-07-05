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
g_user.add_argument('wxtype', location='args')

@n_auth.route('')
class AuthApi(Resource):
    @api.expect(g_user)
    def get(self):
        args = g_user.parse_args()
        if args['Authorization']: # basic auth
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
        elif args['wxcode']: # wx auth
            url = '' # step 1: get access code from client.
            if args['wxtype'] == 'gz':
                url = "https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code" % \
                    (app.config['WX_GZ_APPID'],
                    app.config['WX_GZ_APPSECRET'], args['wxcode'])
            elif args['wxtype'] == 'kf':
                url = "https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code" % \
                    (app.config['WX_KF_APPID'],
                    app.config['WX_KF_APPSECRET'], args['wxcode'])
            try: # step 2: get access_token from wechat serves.
                r = requests.get(url)
                json = r.json()
                if 'access_token' in json:
                    url = "https://api.weixin.qq.com/sns/userinfo?access_token=%s&openid=%s" % \
                        (json['access_token'], json['openid'])
                    try: # step 3: get userinfo with access_token from wechat serves.
                        r = requests.get(url)
                        r.encoding = 'utf-8'
                        json = r.json()
                        if 'openid' in json:
                            wx_user = WxUser.query.filter_by(
                                unionid=json['unionid']).first()
                            # check if the wechat unionid is already registed on our serves
                            if wx_user: # if so, update his info
                                wx_user.openid = json['openid'],
                                wx_user.nickname = json['nickname'],
                                wx_user.sex = json['sex'],
                                wx_user.language = json['language'],
                                wx_user.city = json['city'],
                                wx_user.province = json['province'],
                                wx_user.country = json['country'],
                                wx_user.headimg_url = json['headimgurl'],
                                wx_user.unionid = json['unionid']
                            else: # otherwise, create a new one
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

                                # create a new account on our serves and bind it to the wechat account.
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
                            # generate a jwt based on user id
                            token = jwt.encode({'id': wx_user.bind_user_id, 'exp': datetime.utcnow(
                            )+timedelta(hours = 24)}, app.config['SECRET_KEY'])
                            return {
                                'token': token.decode('UTF-8'),
                                'wx_info': json
                            }, 200
                        else:
                            return json, 400
                    except Exception as e:
                        print(e)
                        return api.abort(400, "bad connection")
                else:
                    return json, 400
            except Exception as e:
                print(e)
                return api.abort(400, "bad connection")
        else:
            return api.abort(400, "bad auth")
