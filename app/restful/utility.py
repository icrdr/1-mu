from ..model import Stage, Phase, User, File, Project, Tag, Group, ProjectNotice, Course
from sqlalchemy import or_, case, and_
from .. import api, app, db
from numpy import interp, clip
from datetime import datetime, timedelta
import math
import time
import hashlib


def getData(user_id, date_range=None):
    user = User.query.get(user_id)
    if not user:
        raise Exception("User is not exist!")

    if date_range:
        start = datetime.strptime(
            date_range[0], '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(
            date_range[1], '%Y-%m-%d %H:%M:%S')
    else:
        start = user.reg_date
        end = datetime.utcnow()

    delta_time = end-start

    stages_all = Stage.query\
        .filter(Stage.phases.any(and_(Phase.upload_date <= end, Phase.upload_date >= start)))\
        .filter(Stage.phases.any(Phase.creator_user_id == user_id)).all()
    stages_one_pass_c = []
    stages_mod_pass_c = []
    stages_no_pass_c = []
    stages_one_pass_d = []
    stages_mod_pass_d = []
    stages_no_pass_d = []
    for stage in stages_all:
        if not stage.phases[-1].feedback_date:
            # print('未完成的阶段：%s-%s'%(stage.project, stage))
            if stage.name == '草图':
                stages_no_pass_d.append(stage)
            else:
                stages_no_pass_c.append(stage)
        else:
            # print('完成的阶段：%s-%s'%(stage.project, stage))
            if len(stage.phases) > 1:
                if stage.name == '草图':
                    stages_mod_pass_d.append(stage)
                else:
                    stages_mod_pass_c.append(stage)
            else:
                if stage.name == '草图':
                    stages_one_pass_d.append(stage)
                else:
                    stages_one_pass_c.append(stage)

    phases_all = Phase.query\
        .filter(and_(Phase.upload_date <= end, Phase.upload_date >= start))\
        .filter(Phase.creator_user_id == user_id).all()
    phases_pass = []
    phases_modify = []
    phases_pending = []
    for phase in phases_all:
        stage = phase.stage
        if phase.feedback_date:
            if stage.phases[-1] == phase:
                phases_pass.append(phase)
            else:
                phases_modify.append(phase)
        else:
            phases_pending.append(phase)

    phases_overtime = []
    overtime_sum = 0
    for phase in phases_all:
        duration = phase.upload_date - phase.deadline_date
        duration_in_s = int(duration.total_seconds())
        if duration_in_s > 0:
            phases_overtime.append(phase)
            overtime_sum += duration_in_s

    files_ref = File.query.filter(File.public == True)\
        .filter(and_(File.upload_date <= end, File.upload_date >= start))\
        .filter(File.uploader_user_id == user_id).all()

    project_sample = Project.query.filter(Project.tags.any(Tag.name == '样图'))\
        .filter(and_(Project.finish_date <= end, Project.finish_date >= start))\
        .filter(Project.phases.any(Phase.creator_user_id == user_id)).all()

    return {
        'user': user,
        'delta_time': delta_time,
        'overtime_sum': overtime_sum,
        'phases_overtime': phases_overtime,
        'phases_all': phases_all,
        'phases_pass': phases_pass,
        'phases_modify': phases_modify,
        'phases_pending': phases_pending,
        'stages_all': stages_all,
        'stages_one_pass_c': stages_one_pass_c,
        'stages_mod_pass_c': stages_mod_pass_c,
        'stages_no_pass_c': stages_no_pass_c,
        'stages_one_pass_d': stages_one_pass_d,
        'stages_mod_pass_d': stages_mod_pass_d,
        'stages_no_pass_d': stages_no_pass_d,
        'files_ref': files_ref,
        'project_sample': project_sample,
    }


def getAttr(data_raw):
    stages_one_pass_c = data_raw['stages_one_pass_c']
    stages_mod_pass_c = data_raw['stages_mod_pass_c']
    stages_c = stages_one_pass_c + stages_mod_pass_c
    phases_count = 0
    for stage in stages_c:
        phases_count += len(stage.phases)

    if stages_c:
        power = (1-phases_count/(len(stages_c)*5))
        power = clip(power, 0, 4/5)
        power = interp(power, [0, 4/5], [1, 5])
    else:
        power = 0

    stages_one_pass_d = data_raw['stages_one_pass_d']
    stages_mod_pass_d = data_raw['stages_mod_pass_d']
    stages_d = stages_one_pass_d + stages_mod_pass_d
    phases_d_count = 0
    for stage in stages_d:
        phases_d_count += len(stage.phases)

    if stages_d:
        knowledge = (1-phases_d_count/(len(stages_d)*5))
        knowledge = clip(knowledge, 0, 4/5)
        knowledge = interp(knowledge, [0, 4/5], [1, 5])

    else:
        knowledge = 0

    power = (knowledge*1 + power*2)/3

    phases_all = data_raw['phases_all']
    delta_time = data_raw['delta_time']
    delta_days = delta_time.days
    if phases_all and delta_days >= 1:
        phases_sort = sorted(phases_all, key=lambda x: x.upload_date)
        ud_total = timedelta(seconds=0)
        dd_total = timedelta(seconds=0)
        for phase in phases_sort:
            ud = phase.upload_date - phase.start_date
            dd = phase.deadline_date - phase.start_date
            pd = timedelta(seconds=0)
            for pause in phase.pauses:
                if phase.upload_date > pause.pause_date and pause.resume_date:
                    pd += pause.resume_date - pause.pause_date
            ud_total += ud - pd
            dd_total += dd - pd
        speed = math.atan(dd_total.total_seconds()*0.8 /
                          ud_total.total_seconds())/(math.pi/2)
        speed = interp(speed, [0, 1], [0, 5])

        energy = len(phases_sort)*1.8/delta_time.days
        energy = clip(energy, 0, 2)
        energy = interp(energy, [0, 2], [1, 5])
    else:
        energy = 0
        speed = 0
    user = data_raw['user']
    files_ref = data_raw['files_ref']
    project_sample = data_raw['project_sample']
    overtime_sum = data_raw['overtime_sum']

    files_s = 0
    for file in files_ref:
        if len(file.tags) < 4:
            files_s += 1
        elif len(file.tags) < 6:
            files_s += 3
        elif len(file.tags) < 8:
            files_s += 5
        elif len(file.tags) < 10:
            files_s += 6
        else:
            files_s += 7

    contribution_s = (len(stages_d)+len(stages_c))*10 + \
        files_s + len(project_sample)*20
    if delta_days >= 1 and contribution_s > 0:
        contribution = contribution_s/delta_days/6
        contribution = clip(contribution, 0, 2)
        contribution = interp(contribution, [0, 2], [1, 5])
    else:
        contribution = 0

    files_s2 = 0
    for file in files_ref:
        if len(file.tags) < 4:
            files_s2 += 1
        elif len(file.tags) < 7:
            files_s2 += 2
        else:
            files_s2 += 3

    score = len(stages_d)*10+len(stages_c)*20 + files_s2 + \
        len(project_sample)*30-overtime_sum/86400
    score = max(score, 0)
    return {
        'power': round(power, 1),
        'speed': round(speed, 1),
        'knowledge': round(knowledge, 1),
        'energy': round(energy, 1),
        'contribution': round(contribution, 1),
        'score': round(score),
    }


def projectCheck(project_id):
    project = Project.query.get(project_id)
    if not project:
        api.abort(400, "Project is not exist.")
    else:
        return project


def userCheck(user_id):
    user = User.query.get(user_id)
    if not user:
        api.abort(400, "user is not exist.")
    else:
        return user


def groupCheck(group_id):
    group = Group.query.get(group_id)
    if not group:
        api.abort(400, "group is not exist.")
    else:
        return group


def projectNoticeCheck(notice_id):
    notice = ProjectNotice.query.get(notice_id)
    if not notice:
        api.abort(400, "notice is not exist.")
    else:
        return notice

def CourseCheck(course_id):
    course = Course.query.get(course_id)
    if not course:
        api.abort(400, "course is not exist.")
    else:
        return course
