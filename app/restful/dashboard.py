
from numpy import interp, clip
from flask_restplus import Resource, reqparse, fields, marshal
from flask import g
from sqlalchemy import or_, case, and_
from .. import api, app, db
from ..model import Stage, Phase, User, File, Project, Tag, Group
from ..utility import buildUrl, getAvatar
from .utility import getData, projectCheck, userCheck, getAttr
from .decorator import permission_required, admin_required
import time
from datetime import datetime, timedelta
import math

N_DASH = api.namespace('api/dashboard', description='projects operations')

GET_DASH = reqparse.RequestParser()\
    .add_argument('date_range', location='args', action='split')\

@N_DASH.route('/data/<int:user_id>')
class DashboardApi(Resource):
    def get(self, user_id):
        args = GET_DASH.parse_args()
        user = userCheck(user_id)
        data_raw = getData(user_id, args['date_range'])
        return {
            'overtime_sum': data_raw['overtime_sum'],
            'phases_overtime': len(data_raw['phases_overtime']),
            'phases_all': len(data_raw['phases_all']),
            'phases_pass': len(data_raw['phases_pass']),
            'phases_modify': len(data_raw['phases_modify']),
            'phases_pending': len(data_raw['phases_pending']),
            'stages_all': len(data_raw['stages_all']),
            'stages_one_pass': len(data_raw['stages_one_pass']),
            'stages_mod_pass': len(data_raw['stages_mod_pass']),
            'stages_no_pass': len(data_raw['stages_no_pass']),
            'stages_one_pass_d': len(data_raw['stages_one_pass_d']),
            'stages_mod_pass_d': len(data_raw['stages_mod_pass_d']),
            'stages_no_pass_d': len(data_raw['stages_no_pass_d']),
            'files_ref': len(data_raw['files_ref']),
            'project_sample': len(data_raw['project_sample']),
        }, 200

@N_DASH.route('/attr/<int:user_id>')
class DashboardDataApi(Resource):
    def get(self, user_id):
        args = GET_DASH.parse_args()
        user = userCheck(user_id)
        data_raw = getData(user_id, args['date_range'])
        return getAttr(data_raw), 200
