"""
Project Stage Phase Propose
"""

from datetime import datetime, timedelta
from .. import db, scheduler, app
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
    # meta data
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    design = db.Column(db.Text)
    remark = db.Column(db.Text)
    files = db.relationship('File', secondary=PROJECT_FILE,
                            lazy='subquery', backref=db.backref('projects', lazy=True))
    tags = db.relationship(
        'Tag', secondary=PROJECT_TAG,
        lazy='subquery', backref=db.backref('projects', lazy=True))

    # user data
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref(
        'projects_as_client', lazy=True))

    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    creator = db.relationship('User', foreign_keys=creator_user_id, backref=db.backref(
        'projects_as_creator', lazy=True))

    # progress & status data
    status = db.Column(
        db.Enum('progress', 'modify', 'pending', 'await', 'finish'),
        server_default=("await"))
    progress = db.Column(db.Integer, default=0)
    public = db.Column(db.Boolean, nullable=False, default=False)
    pause = db.Column(db.Boolean, nullable=False, default=False)
    delay = db.Column(db.Boolean, nullable=False, default=False)
    discard = db.Column(db.Boolean, nullable=False, default=False)
    stages = db.relationship(
        'Stage',  foreign_keys='Stage.project_id', backref=db.backref('project', lazy=True))

    # timestamp
    post_date = db.Column(db.DateTime, default=datetime.utcnow)
    # just for query more earily
    start_date = db.Column(db.DateTime)
    finish_date = db.Column(db.DateTime)
    deadline_date = db.Column(db.DateTime)

    def current_stage(self):
        """Get current stage."""
        if self.progress <= 0:
            return None
        else:
            return self.stages[self.progress-1]

    def current_phase(self):
        """Get current phase."""
        if not self.current_stage():
            return None
        if self.current_stage().phases:
            return self.current_stage().phases[-1]
        else:
            return None

    def doStart(self, operator_id):
        """Start this project."""
        if self.discard:
            raise Exception("Discard project can't start!")

        # setting project status & progress
        self.status = 'progress'
        self.progress = 1
        self.start_date = datetime.utcnow()

        # add new phase
        current_stage = self.current_stage()
        deadline = datetime.utcnow() + timedelta(days=current_stage.days_planned)
        new_phase = Phase(
            stage=current_stage,
            project=self,
            deadline_date=deadline
        )
        db.session.add(new_phase)
        self.deadline_date = deadline
        # logging
        new_log = ProjectLog(
            project=self,
            phase=new_phase,
            log_type='start',
            operator_user_id=operator_id
        )
        db.session.add(new_log)

        # create a new delay counter
        addDelayCounter(self.id, deadline)
        db.session.commit()
        return self

    def editUpload(self, operator_id, creator_id, upload, upload_files):
        current_phase = self.current_phase()
        current_phase.creator_user_id = creator_id
        current_phase.creator_upload = upload
        current_phase.upload_files = []
        for upload_file in upload_files:
            current_phase.upload_files.append(
                File.query.get(upload_file['id']))

        db.session.commit()

    def doUpload(self, operator_id, creator_id, upload_content, upload_files):
        """upload current stage."""
        if self.discard or self.pause:
            raise Exception("Discard or paused project can't upload!")
        # current phase update
        current_phase = self.current_phase()
        current_phase.creator_user_id = creator_id
        current_phase.creator_upload = upload_content
        current_phase.upload_files = []
        for upload_file in upload_files:
            current_phase.upload_files.append(
                File.query.get(upload_file['id']))
        current_phase.upload_date = datetime.utcnow()

        # project update
        self.status = 'pending'
        self.delay = False

        # logging
        new_log = ProjectLog(
            project=self,
            phase=current_phase,
            log_type='upload',
            content=upload_content,
            operator_user_id=operator_id
        )
        db.session.add(new_log)
        self.deadline_date = None
        # stop the delay counter
        removeDelayCounter(self.id)
        db.session.commit()
        return self

    def editFeedback(self, operator_id, client_id, feedback_content):
        """Set the status to 'modify'."""
        # current phase update
        current_phase = self.current_phase()
        current_phase.client_feedback = feedback_content
        current_phase.client_user_id = client_id
        db.session.commit()
        return self

    def doFeedback(self, operator_id, client_id, feedback_content, is_pass):
        """Set the status to 'modify'."""
        if self.discard or self.pause:
            raise Exception("Discard or paused project can't set to modify!")

        # current phase update
        current_phase = self.current_phase()
        current_phase.client_feedback = feedback_content
        current_phase.client_user_id = client_id
        current_phase.feedback_date = datetime.utcnow()

        if is_pass:
            # if current stage is not the last one, then go into next stage
            if self.progress < len(self.stages):
                # project update
                self.progress += 1
                self.status = 'progress'

                # next stage phase update
                next_stage = self.current_stage()

                deadline = datetime.utcnow() + timedelta(days=next_stage.days_planned)
                new_phase = Phase(
                    project=self,
                    stage=next_stage,
                    deadline_date=deadline
                )
                db.session.add(new_phase)
                self.deadline_date = deadline
                # create a new delay counter
                addDelayCounter(self.id, deadline)
            else:
                # project update
                self.progress = -1
                self.status = 'finish'
                self.finish_date = datetime.utcnow()
        else:
            # project update
            self.status = 'modify'

            # craete new phase in current stage
            current_stage = self.current_stage()
            days_required = math.floor(current_stage.days_planned*0.2)+1
            deadline = datetime.utcnow() + timedelta(days=days_required)
            new_phase = Phase(
                project=self,
                stage=current_stage,
                deadline_date=deadline
            )
            db.session.add(new_phase)
            self.deadline_date = deadline
            # create a new delay counter
            addDelayCounter(self.id, deadline)

        # logging
        new_log = ProjectLog(
            project=self,
            phase=current_phase,
            log_type=('modify', 'pass')[is_pass],
            content=feedback_content,
            operator_user_id=operator_id
        )
        db.session.add(new_log)
        db.session.commit()

    def doChangeStage(self, operator_id, progress_index):
        """change stage"""
        if self.discard or self.pause:
            raise Exception("Discard or paused project can't change stage!")

        current_phase = self.current_phase()
        if current_phase:
            db.session.delete(current_phase)
        self.progress = progress_index
        self.finish_date = None

        if progress_index == 0 or progress_index == -1:
            self.delay = False
            self.deadline_date = None

            if progress_index == 0:
                self.status = 'await'
                self.start_date = None
            else:
                self.status = 'finish'
                self.finish_date = datetime.utcnow()
            
            removeDelayCounter(self.id)
        else:
            next_stage = self.stages[progress_index-1]
            deadline = datetime.utcnow() + timedelta(days=next_stage.days_planned)
            new_phase = Phase(
                project=self,
                stage=next_stage,
                deadline_date=deadline
            )
            db.session.add(new_phase)
            self.deadline_date = deadline
            addDelayCounter(self.id, deadline)

            self.status = 'progress'

        # logging
        new_log = ProjectLog(
            project=self,
            log_type='stage',
            operator_user_id=operator_id
        )
        db.session.add(new_log)
        db.session.commit()

    def doDiscard(self, operator_id):
        """Discard this project."""
        if self.progress > 0:
            self.doPause(operator_id, logging=False)

        # update projcet
        self.discard = True

        # logging
        new_log = ProjectLog(
            project=self,
            phase=self.current_phase(),
            log_type='discard',
            operator_user_id=operator_id
        )
        db.session.add(new_log)
        db.session.commit()

    def doRecover(self, operator_id):
        """Recover this project."""
        # update projcet
        self.discard = False

        # logging
        new_log = ProjectLog(
            project=self,
            log_type='recover',
            operator_user_id=operator_id
        )
        db.session.add(new_log)

        db.session.commit()

        if self.pause:
            self.doResume(operator_id, logging=False)

    def doPause(self, operator_id, logging=True):
        """Pause this project."""
        if self.discard or self.progress == 0 or self.progress == -1:
            raise Exception("Discard project can't pause!")

        # current phase update
        current_phase = self.current_phase()
        if current_phase:
            new_pause = ProjectPause(
                pause_date=datetime.utcnow()
            )
            db.session.add(new_pause)
            current_phase.pauses.append(new_pause)
            self.deadline_date = None
            # stop the delay counter
            removeDelayCounter(self.id)

        # update projcet
        self.pause = True

        # logging
        if logging:
            new_log = ProjectLog(
                project=self,
                phase=current_phase,
                log_type='pause',
                operator_user_id=operator_id
            )
            db.session.add(new_log)
        db.session.commit()

    def doResume(self, operator_id, logging=True):
        """Resume this project."""
        if self.discard or self.progress == 0 or self.progress == -1:
            raise Exception("Discard project can't resume!")

        # update phase deadline
        current_phase = self.current_phase()
        if current_phase:
            offset = datetime.utcnow() - current_phase.pauses[-1].pause_date
            deadline = current_phase.deadline_date + offset
            current_phase.deadline_date = deadline
            current_phase.pauses[-1].resume_date = datetime.utcnow()
            self.deadline_date = deadline
            # create a new delay counter
            addDelayCounter(self.id, deadline)

        # update projcet
        self.pause = False

        # logging
        if logging:
            new_log = ProjectLog(
                project=self,
                phase=current_phase,
                log_type='resume',
                operator_user_id=operator_id
            )
            db.session.add(new_log)
        db.session.commit()

    def doChangeDDL(self, operator_id, deadline):
        """change the current ddl."""
        if self.progress <= 0:
            raise Exception("Project is not in progress!")

        # current phase update
        current_phase = self.current_phase()
        current_phase.deadline_date = deadline
        self.deadline_date = deadline
        if deadline < datetime.utcnow():
            self.delay = True
        else:
            self.delay = False
            # create a new delay counter
            addDelayCounter(self.id, deadline)

        new_log = ProjectLog(
            project=self,
            phase=current_phase,
            log_type='deadline',
            operator_user_id=operator_id
        )
        db.session.add(new_log)
        db.session.commit()

    def doDelete(self):
        """Delete this project."""
        pauses = self.pauses
        for pause in pauses:
            db.session.delete(pause)

        files = self.files
        for file in files:
            db.session.delete(file)

        logs = self.logs
        for log in logs:
            db.session.delete(log)

        phases = self.phases
        for phase in phases:
            db.session.delete(phase)

        stages = self.stages
        for stage in stages:
            db.session.delete(stage)

        db.session.delete(self)
        removeDelayCounter(self.id)
        db.session.commit()

    @staticmethod
    def delete_all_project():
        projects = Project.query.all()
        for project in projects:
            project.doDelete()
        print('all project deleted.')

    @staticmethod
    def create_project(operator_id, title, client_id, creator_id, design, stages, tags, files):
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
                project=new_project,
                days_planned=stage['days_planned']
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

        new_log = ProjectLog(
            project=new_project,
            log_type='create',
            operator_user_id=operator_id
        )
        db.session.add(new_log)

        db.session.commit()
        return new_project

    def __repr__(self):
        return '<Project id %s %s>' % (self.id, self.title)


class Stage(db.Model):
    """Stage Model"""
    __tablename__ = 'stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    description = db.Column(db.String(512))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    days_planned = db.Column(db.Integer)
    def __repr__(self):
        return '<Stage id %s>' % self.id


class Phase(db.Model):
    """Phase Model"""
    __tablename__ = 'phases'
    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    project = db.relationship('Project', foreign_keys=project_id, order_by="Phase.start_date", backref=db.backref(
        'phases', lazy=True))

    stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'))
    stage = db.relationship('Stage', foreign_keys=stage_id, order_by="Phase.start_date", backref=db.backref(
        'phases', lazy=True))

    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    creator = db.relationship('User', foreign_keys=creator_user_id, backref=db.backref(
        'phases_as_creator', lazy=True))
    creator_upload = db.Column(db.Text)

    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref(
        'phases_as_client', lazy=True))
    client_feedback = db.Column(db.Text)

    # time stamp
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    deadline_date = db.Column(db.DateTime)
    upload_date = db.Column(db.DateTime)
    feedback_date = db.Column(db.DateTime)

    # many-many: File.phases-Phase.files
    upload_files = db.relationship('File', secondary=PHASE_UPLOAD_FILE,
                                   lazy='subquery', backref=db.backref('phases_as_upload', lazy=True))

    # many-many: File.phases-Phase.files
    files = db.relationship('File', secondary=PHASE_FILE,
                            lazy='subquery', backref=db.backref('phases', lazy=True))

    def __repr__(self):
        return '<Phase id %s>' % self.id


class ProjectPause(db.Model):
    """Pause Model"""
    __tablename__ = 'project_pauses'
    id = db.Column(db.Integer, primary_key=True)
    pause_date = db.Column(db.DateTime)
    resume_date = db.Column(db.DateTime)
    reason = db.Column(db.String(512))

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    project = db.relationship('Project', foreign_keys=project_id, backref=db.backref(
        'pauses', lazy=True))

    phase_id = db.Column(db.Integer, db.ForeignKey('phases.id'))
    phase = db.relationship('Phase', foreign_keys=phase_id, backref=db.backref(
        'pauses', lazy=True))

    def __repr__(self):
        return '<ProjectPause id %s>' % self.id


class ProjectLog(db.Model):
    """ProjectLog Model"""
    __tablename__ = 'project_logs'
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.DateTime, default=datetime.utcnow)

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    project = db.relationship('Project', foreign_keys=project_id, backref=db.backref(
        'logs', lazy=True))

    phase_id = db.Column(db.Integer, db.ForeignKey('phases.id'))
    phase = db.relationship('Phase', foreign_keys=phase_id, backref=db.backref(
        'logs', lazy=True))

    log_type = db.Column(
        db.Enum('create', 'start', 'upload', 'pass', 'modify', 'discard', 'recover',
                'pause', 'resume', 'deadline', 'design', 'stage'),
        server_default=("start"))

    content = db.Column(db.Text)

    # remove it
    read = db.Column(db.Boolean, nullable=False, default=False)

    operator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    operator = db.relationship('User', foreign_keys=operator_user_id, backref=db.backref(
        'project_logs_as_operator', lazy=True))

    def set_read(self):
        self.read = True
        self.read_date = datetime.utcnow()
        db.session.commit()
        return self

    def __repr__(self):
        return '<ProjectLog id %s>' % self.id


def delay(project_id):
    project = Project.query.get(project_id)
    if project.status == 'modify' or project.status == 'progress':
        project.delay = True
    db.session.commit()
    print('%d project delay!' % project_id)


def addDelayCounter(project_id, deadline):
    scheduler.add_job(
        id='delay_project_' + str(project_id),
        func=delay,
        args=[project_id],
        trigger='date',
        run_date=deadline,
        replace_existing=True,
        misfire_grace_time=2592000
    )
    print('%d project addCounter: %s' % (project_id, deadline))


def removeDelayCounter(project_id):
    if scheduler.get_job('delay_project_'+str(project_id)):
        scheduler.remove_job('delay_project_'+str(project_id))
        print('%d project removeCounter' % project_id)


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
