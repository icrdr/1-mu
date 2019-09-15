from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from sqlalchemy import or_, case, and_
from .. import api, app, db
from ..model import Option, Phase, User, File, Project, Tag, Group
from ..utility import buildUrl, getAvatar
from .utility import getData, projectCheck, userCheck
from .decorator import permission_required, admin_required
import time
from datetime import datetime

N_OPTION = api.namespace('api/options', description='option operations')

UPDATE_OPTION = reqparse.RequestParser()\
    .add_argument('allow_sign_in')\

@N_OPTION.route('')
class OptionsApi(Resource):
    @permission_required()
    def get(self):
        allow_sign_in = Option.query.filter_by(name='allow_sign_in').first()
        return {
            'allow_sign_in': allow_sign_in.value,
        }, 200
    
    @permission_required()
    def put(self):
        args = UPDATE_OPTION.parse_args()
        allow_sign_in = Option.query.filter_by(name='allow_sign_in').first()
        allow_sign_in.value = args['allow_sign_in']
        db.session.commit()
        return {
            'message': 'ok',
        }, 200
