"""
Project Stage Phase Propose
"""

from datetime import datetime, timedelta
from .. import db, scheduler
from .user import User, Group
from .misc import Option
from .file import File
from .post import Tag
import math
import json
import requests
from ..utility import UTC2Local, excerptHtml, word2List, getPhaseIndex, getStageIndex

PROJECT_TAG = db.Table(
    'project_tags',
    db.Column('tag_id', db.Integer,
              db.ForeignKey('tags.id')),
    db.Column('project_id', db.Integer,
              db.ForeignKey('projects.id')),
)
PHASE_FILE = db.Table(
    'phase_files',
    db.Column('file_id', db.Integer,
              db.ForeignKey('files.id')),
    db.Column('phase_id', db.Integer,
              db.ForeignKey('phases.id')),
)
PROJECT_FILE = db.Table(
    'project_files',
    db.Column('file_id', db.Integer,
              db.ForeignKey('files.id')),
    db.Column('project_id', db.Integer,
              db.ForeignKey('projects.id')),
)
PHASE_UPLOAD_FILE = db.Table(
    'phase_upload_files',
    db.Column('upload_file_id', db.Integer,
              db.ForeignKey('files.id')),
    db.Column('phase_id', db.Integer,
              db.ForeignKey('phases.id')),
)


class Project(db.Model):
    """Project Model"""
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    design = db.Column(db.Text)
    remark = db.Column(db.Text)
    # one-many: Post.client-User.projects_as_client
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref(
        'projects_as_client', lazy=True))

    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    creator = db.relationship('User', foreign_keys=creator_user_id, backref=db.backref(
        'projects_as_creator', lazy=True))

    # many-many: User.projects-Project.creators
    creator_group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    creator_group = db.relationship('Group', foreign_keys=creator_group_id, backref=db.backref(
        'projects', lazy=True))
    # many-many: User.projects-Project.creators
    tags = db.relationship(
        'Tag', secondary=PROJECT_TAG,
        lazy='subquery', backref=db.backref('projects', lazy=True))

    status = db.Column(
        db.Enum('draft', 'await', 'progress', 'delay', 'pending',
                'abnormal', 'modify', 'pause', 'finish', 'discard'),
        server_default=("draft"))
    post_date = db.Column(db.DateTime, default=datetime.utcnow)
    start_date = db.Column(db.DateTime)
    finish_date = db.Column(db.DateTime)

    # remove it
    last_pause_date = db.Column(db.DateTime)

    # one-many: project.client-User.projects_as_client
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref(
        'projects_as_client', lazy=True))
    # many-many: File.phases-Phase.files
    files = db.relationship('File', secondary=PROJECT_FILE,
                            lazy='subquery', backref=db.backref('projects', lazy=True))
    # one-many: Comment.parent_post-Post.comments
    stages = db.relationship(
        'Stage', backref=db.backref('parent_project', lazy=True))
    phases = db.relationship(
        'Phase', order_by="Phase.start_date", backref=db.backref('parent_project', lazy=True))
    current_stage_index = db.Column(db.Integer, default=0)

    # one-many: Propose.parent_project-Project.Proposes
    proposes = db.relationship(
        'Propose', backref=db.backref('parent_project', lazy=True))

    notices = db.relationship(
        'ProjectNotice', backref=db.backref('parent_project', lazy=True))

    def current_stage(self):
        """Get current stage."""
        return self.stages[self.current_stage_index]

    def current_phase(self):
        """Get current phase."""
        if self.current_stage().phases:
            return self.current_stage().phases[-1]
        else:
            return False

    def start(self):
        """Start this project."""
        # start project
        self.status = 'progress'
        self.start_date = datetime.utcnow()

        deadline = datetime.utcnow() + timedelta(days=self.current_stage().days_need)
        new_phase = Phase(
            parent_stage=self.current_stage(),
            parent_project=self,
            start_date=datetime.utcnow(),
            deadline_date=deadline
        )
        db.session.add(new_phase)

        # create a new delay counter
        addDelayCounter(self.id, deadline)
        db.session.commit()
        return self

    def modify(self, client_id, feedback, confirm):
        """Set the status to 'modify'."""
        # current phase update
        self.current_phase().client_feedback = feedback
        self.current_phase().client_user_id = client_id

        if confirm:
            # add notice
            new_notice = ProjectNotice(
                parent_project_id=self.id,
                parent_stage_id=self.current_stage().id,
                parent_phase_id=self.current_phase().id,
                from_user_id=client_id,
                to_user_id=self.creator.id,
                notice_type='modify',
                content=feedback
            )
            db.session.add(new_notice)

            self.status = 'modify'
            self.current_phase().feedback_date = datetime.utcnow()
            # craete new phase in current stage
            new_phase = Phase(
                parent_project=self,
                parent_stage=self.current_stage(),
            )
            days_need = math.floor(self.current_stage(
            ).days_need*0.2)+1
            db.session.add(new_phase)
            deadline = datetime.utcnow() + timedelta(days=days_need)

            new_phase.deadline_date = deadline
            wx_message(new_notice)
            # create a new delay counter
            addDelayCounter(self.id, deadline)
        db.session.commit()
        return self

    def finish(self, client_id, feedback):
        """Finish current stage."""
        # add notice
        new_notice = ProjectNotice(
            parent_project_id=self.id,
            parent_stage_id=self.current_stage().id,
            parent_phase_id=self.current_phase().id,
            from_user_id=client_id,
            to_user_id=self.creator.id,
            notice_type='pass',
            content=feedback
        )
        db.session.add(new_notice)

        # current phase update
        self.status = 'finish'
        self.current_phase().feedback_date = datetime.utcnow()
        self.current_phase().client_feedback = feedback
        self.current_phase().client_user_id = client_id
        nextStageStart(self)
        wx_message(new_notice)
        db.session.commit()
        return self

    def upload(self, creator_id, upload, upload_files, confirm):
        """upload current stage."""
        # current phase update
        self.current_phase().creator_user_id = creator_id
        self.current_phase().creator_upload = upload
        self.current_phase().upload_files = []
        for upload_file in upload_files:
            self.current_phase().upload_files.append(
                File.query.get(upload_file['id']))

        if confirm:
            self.status = 'pending'
            self.current_phase().upload_date = datetime.utcnow()
            # add notice
            new_notice = ProjectNotice(
                parent_project_id=self.id,
                parent_stage_id=self.current_stage().id,
                parent_phase_id=self.current_phase().id,
                from_user_id=creator_id,
                to_user_id=self.client.id,
                notice_type='upload',
                content=upload
            )
            cover_file = File.query.get(upload_files[0]['id'])
            if cover_file.previews:
                new_notice.cover_url = cover_file.previews[0].url
            db.session.add(new_notice)
            wx_message(new_notice)
            # stop the delay counter
            removeDelayCounter(self.id)
        db.session.commit()
        return self

    def goBack(self):
        """go back"""
        print('go back')
        if self.status == 'finish':
            deadline = datetime.utcnow() + timedelta(days=self.current_stage().days_need)
            new_phase = Phase(
                parent_stage=self.current_stage(),
                parent_project=self,
                start_date=datetime.utcnow(),
                deadline_date=deadline
            )
            db.session.add(new_phase)
            self.status = 'progress'
            addDelayCounter(self.id, deadline)
            db.session.commit()
        elif self.current_stage_index > 0:
            self.current_stage().phases = []
            self.current_stage_index -= 1
            deadline = datetime.utcnow() + timedelta(days=self.current_stage().days_need)
            new_phase = Phase(
                parent_stage=self.current_stage(),
                parent_project=self,
                start_date=datetime.utcnow(),
                deadline_date=deadline
            )
            db.session.add(new_phase)
            self.status = 'progress'
            addDelayCounter(self.id, deadline)
            db.session.commit()
        else:
            self.current_stage().phases = []
            self.status = 'await'
            removeDelayCounter(self.id)
            db.session.commit()
        return self

    def discard(self):
        """Discard this project."""
        # current phase update
        self.status = 'discard'
        if self.current_phase():
            new_pause = PhasePause(
                pause_date=datetime.utcnow()
            )
            db.session.add(new_pause)
            self.current_phase().pauses.append(new_pause)
            # stop the delay counter
            removeDelayCounter(self.id)
            db.session.commit()
        return self

    def resume(self):
        """Resume this project."""
        # current phase update
        if self.current_phase():
            if self.current_phase().feedback_date:
                self.status = 'finish'
                nextStageStart(self)
            elif self.current_phase().upload_date:
                self.status = 'pending'
            elif self.current_phase().start_date:
                if len(self.current_stage().phases) > 1:
                    self.status = 'modify'
                else:
                    self.status = 'progress'

                # create a new delay counter
                offset = self.current_phase().start_date - \
                    self.current_phase().pauses[-1].pause_date
                if timedelta(days=self.current_stage().days_need) > self.current_phase().pauses[-1].pause_date - self.current_phase().start_date:
                    deadline = datetime.utcnow() + timedelta(days=self.current_stage().days_need) + offset
                    self.current_phase().deadline_date = deadline
                    addDelayCounter(self.id, deadline)
                else:
                    self.status = 'delay'
            else:
                self.status = 'await'
            self.current_phase().pauses[-1].resume_date = datetime.utcnow()
        else:
            self.status = 'await'
        db.session.commit()
        return self

    def postpone(self, days):
        """postpone this stage."""
        # current phase update
        
        deadline = self.current_phase().start_date + \
            timedelta(days=self.current_stage().days_need)
        self.current_phase().deadline_date = deadline

        if deadline>datetime.utcnow():
            if len(self.current_stage().phases) > 1:
                self.status = 'modify'
            else:
                self.status = 'progress'

            # create a new delay counter
            addDelayCounter(self.id, deadline)
        db.session.commit()
        return self

    def abnormal(self):
        """Set to abnormal."""
        # current phase update
        self.status = 'abnormal'
        new_pause = PhasePause(
            pause_date=datetime.utcnow()
        )
        db.session.add(new_pause)
        self.current_phase().pauses.append(new_pause)
        # stop the delay counter
        removeDelayCounter(self.id)
        db.session.commit()
        return self

    def pause(self):
        """Set to pause."""
        # current phase update
        self.status = 'pause'
        new_pause = PhasePause(
            pause_date=datetime.utcnow()
        )
        db.session.add(new_pause)
        self.current_phase().pauses.append(new_pause)
        # stop the delay counter
        removeDelayCounter(self.id)
        db.session.commit()
        return self

    def delete(self):
        """Delte this project."""
        stages = self.stages
        for stage in stages:
            phases = stage.phases
            for phase in phases:
                pauses = phase.pauses
                for pause in pauses:
                    db.session.delete(pause)
                db.session.delete(phase)
            db.session.delete(stage)
        db.session.delete(self)
        removeDelayCounter(self.id)
        db.session.commit()

    @staticmethod
    def delete_all_project():
        projects = Project.query.all()
        for project in projects:
            project.delete()
        print('all project deleted.')

    @staticmethod
    def create_project(title, client_id, creator_id, design, stages, tags, files, confirm):
        """Create new project."""
        # create project
        new_project = Project(
            title=title,
            client_user_id=client_id,
            creator_user_id=creator_id,
            design=design
        )
        db.session.add(new_project)

        # create stage
        for stage in stages:
            new_stage = Stage(
                name=stage['stage_name'],
                parent_project=new_project,
                days_need=stage['days_need']
            )
            db.session.add(new_stage)

        if tags:
            all_tag_list = []
            for tag in tags:
                tag_list = word2List(tag)
                all_tag_list += tag_list

            for tag in all_tag_list:
                _tag = Tag.query.filter_by(name=tag).first()
                if not _tag:
                    _tag = Tag(name=tag)
                    db.session.add(_tag)
                new_project.tags.append(_tag)

        if files:
            for file in files:
                _file = File.query.get(file)
                if _file:
                    new_project.files.append(_file)

        if confirm:
            new_project.status = 'await'
        db.session.commit()
        return new_project

    def __repr__(self):
        return '<Project %r>' % self.title


class Stage(db.Model):
    """Stage Model"""
    __tablename__ = 'stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    description = db.Column(db.String(512))
    # one-many: Project.stages-Stage.parent_project
    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))

    days_need = db.Column(db.Integer)

    # one-many: Phase.parent_stage-Stage.phases
    phases = db.relationship(
        'Phase', order_by="Phase.start_date", backref=db.backref('parent_stage', lazy=True))
    notices = db.relationship(
        'ProjectNotice', backref=db.backref('parent_stage', lazy=True))

    def __repr__(self):
        return '<Stage %r>' % self.id


class Phase(db.Model):
    """Phase Model"""
    __tablename__ = 'phases'
    id = db.Column(db.Integer, primary_key=True)
    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    parent_stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'))

    # remove it
    days_need = db.Column(db.Integer)

    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    creator = db.relationship('User', foreign_keys=creator_user_id, backref=db.backref(
        'Phases_as_creator', lazy=True))
    creator_upload = db.Column(db.Text)
    upload_date = db.Column(db.DateTime)

    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref(
        'Phases_as_client', lazy=True))
    client_feedback = db.Column(db.Text)
    feedback_date = db.Column(db.DateTime)

    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    deadline_date = db.Column(db.DateTime)

    # many-many: File.phases-Phase.files
    upload_files = db.relationship('File', secondary=PHASE_UPLOAD_FILE,
                                   lazy='subquery', backref=db.backref('phases_as_upload', lazy=True))

    # many-many: File.phases-Phase.files
    files = db.relationship('File', secondary=PHASE_FILE,
                            lazy='subquery', backref=db.backref('phases', lazy=True))
    notices = db.relationship(
        'ProjectNotice', backref=db.backref('parent_phase', lazy=True))
    pauses = db.relationship(
        'PhasePause', backref=db.backref('parent_phase', lazy=True))

    def __repr__(self):
        return '<Phase %r>' % self.id


class PhasePause(db.Model):
    """Phase pauseModel"""
    __tablename__ = 'phase_pauses'
    id = db.Column(db.Integer, primary_key=True)
    pause_date = db.Column(db.DateTime)
    resume_date = db.Column(db.DateTime)
    reason = db.Column(db.String(512))
    parent_phase_id = db.Column(db.Integer, db.ForeignKey('phases.id'))

    def __repr__(self):
        return '<PhasePause %r>' % self.id


class ProjectNotice(db.Model):
    """ProjectNotice Model"""
    __tablename__ = 'project_notices'
    id = db.Column(db.Integer, primary_key=True)
    send_date = db.Column(db.DateTime, default=datetime.utcnow)
    read_date = db.Column(db.DateTime)

    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    parent_stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'))
    parent_phase_id = db.Column(db.Integer, db.ForeignKey('phases.id'))
    propose_id = db.Column(db.Integer, db.ForeignKey('proposes.id'))

    notice_type = db.Column(
        db.Enum('upload', 'pass', 'modify', 'delay', 'propose'),
        server_default=("upload"))

    content = db.Column(db.Text)
    cover_url = db.Column(db.String(512))
    read = db.Column(db.Boolean, default=False)

    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    from_user = db.relationship('User', foreign_keys=from_user_id, backref=db.backref(
        'project_notices_as_sender', lazy=True))

    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    to_user = db.relationship('User', foreign_keys=to_user_id, backref=db.backref(
        'project_notices_as_receiver', lazy=True))

    def set_read(self):
        self.read = True
        self.read_date = datetime.utcnow()
        db.session.commit()
        return self

    def __repr__(self):
        return '<ProjectNotice %r>' % self.id


class Propose(db.Model):
    """Propose Model"""
    __tablename__ = 'proposes'
    id = db.Column(db.Integer, primary_key=True)
    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    notice = db.relationship(
        'ProjectNotice', backref='propose', uselist=False)
    proposer_role = db.Column(
        db.Enum('creator', 'client'), server_default=("creator"))
    propose_type = db.Column(db.Enum('postpone', 'overhaul'),
                             server_default=("postpone"))
    propose_date = db.Column(db.DateTime)

    def __repr__(self):
        return '<Phase %r>' % self.id


def delay(project_id):
    project = Project.query.get(project_id)
    if project.status == 'modify' or project.status == 'progress':
        project.status = 'delay'
    db.session.commit()
    print('project_'+str(project_id)+': delay!')


def addDelayCounter(project_id, deadline):

    print(deadline)
    scheduler.add_job(
        id='delay_project_' + str(project_id),
        func=delay,
        args=[project_id],
        trigger='date',
        run_date=deadline,
        replace_existing=True,
        misfire_grace_time=2592000
    )
    print('addCounter: '+str(project_id))


def removeDelayCounter(project_id):
    if scheduler.get_job('delay_project_'+str(project_id)):
        scheduler.remove_job('delay_project_'+str(project_id))
        print('removeCounter: '+str(project_id))


def nextStageStart(project):
    # if current stage is not the last one, then go into next stage
    if project.current_stage_index < len(project.stages)-1:
        # next stage phase update
        project.current_stage_index += 1
        next_stage = project.stages[project.current_stage_index]

        project.status = 'progress'

        deadline = datetime.utcnow() + timedelta(days=next_stage.days_need)
        new_phase = Phase(
            parent_stage=next_stage,
            parent_project=project,
            deadline_date=deadline
        )
        db.session.add(new_phase)

        # create a new delay counter
        addDelayCounter(project.id, deadline)
    else:
        project.finish_date = datetime.utcnow()


def wx_message(notice):
    option = Option.query.filter_by(name='wechat_access_token').first()
    if not option:
        return False
    if not notice.to_user.wx_user:
        return False

    url = "https://api.weixin.qq.com/cgi-bin/message/template/send"
    params = {
        "access_token": option.value,
    }
    if notice.notice_type == 'upload':
        data = {
            "touser": notice.to_user.wx_user.openid,
            "template_id": "36lVWBBzRu_Fw5qFwLJzf-1ZTwdn850QUQ7Q653ulww",
            "url": "http://beta.1-mu.net/projects/{}?stage_index={}&phase_index={}".format(notice.parent_project_id, getStageIndex(notice.parent_stage), getPhaseIndex(notice.parent_phase)),
            "data": {
                "first": {
                    "value": "企划名：{}-{}".format(notice.parent_project.title, notice.parent_stage.name),
                },
                "keyword1": {
                    "value": "{} 提交了阶段成品".format(notice.from_user.name),
                    "color": "#8c8c8c"
                },
                "keyword2": {
                    "value": UTC2Local(notice.send_date).strftime("%Y-%m-%d %H:%M:%S"),
                    "color": "#8c8c8c"
                },
                "remark": {
                    "value": "说明：{}".format(excerptHtml(notice.content, 40)),
                    "color": "#8c8c8c"
                }
            }
        }
    elif notice.notice_type == 'modify':
        data = {
            "touser": notice.to_user.wx_user.openid,
            "template_id": "36lVWBBzRu_Fw5qFwLJzf-1ZTwdn850QUQ7Q653ulww",
            "url": "http://beta.1-mu.net/projects/{}?stage_index={}&phase_index={}".format(notice.parent_project_id, getStageIndex(notice.parent_stage), getPhaseIndex(notice.parent_phase)),
            "data": {
                "first": {
                    "value": "企划名：{}-{}".format(notice.parent_project.title, notice.parent_stage.name),
                },
                "keyword1": {
                    "value": "{} 提出了修改建议".format(notice.from_user.name),
                    "color": "#8c8c8c"
                },
                "keyword2": {
                    "value": UTC2Local(notice.send_date).strftime("%Y-%m-%d %H:%M:%S"),
                    "color": "#8c8c8c"
                },
                "remark": {
                    "value": "{} 建议：{}".format(notice.from_user.name, excerptHtml(notice.content, 40)),
                    "color": "#8c8c8c"
                }
            }
        }
    elif notice.notice_type == 'pass':
        data = {
            "touser": notice.to_user.wx_user.openid,
            "template_id": "36lVWBBzRu_Fw5qFwLJzf-1ZTwdn850QUQ7Q653ulww",
            "url": "http://beta.1-mu.net/projects/{}?stage_index={}&phase_index={}".format(notice.parent_project_id, getStageIndex(notice.parent_stage), getPhaseIndex(notice.parent_phase)),
            "data": {
                "first": {
                    "value": "企划名：{}-{}".format(notice.parent_project.title, notice.parent_stage.name),
                },
                "keyword1": {
                    "value": "{} 审核通过当前阶段".format(notice.from_user.name),
                    "color": "#8c8c8c"
                },
                "keyword2": {
                    "value": UTC2Local(notice.send_date).strftime("%Y-%m-%d %H:%M:%S"),
                    "color": "#8c8c8c"
                },
                "remark": {
                    "value": "{} 建议：{}".format(notice.from_user.name, excerptHtml(notice.content, 40)),
                    "color": "#8c8c8c"
                }
            }
        }
    try:
        res = requests.post(url, params=params, data=json.dumps(
            data, ensure_ascii=False).encode('utf-8'))
        data = res.json()
        print('send wx message to {}'.format(notice.to_user.name))

    except Exception as e:
        print(e)
