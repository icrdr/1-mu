from . import db, app
from datetime import datetime
import os
from werkzeug.security import generate_password_hash

PERMISSIONS = {
    'ADMIN': 1,
    'WRITE': 2,
    'EDIT': 4,
    'UPLOAD': 8
}

ROLE_PRESSENT = {
    'ROLES': {
        'Admin': [PERMISSIONS['WRITE'], PERMISSIONS['EDIT'], PERMISSIONS['UPLOAD'], PERMISSIONS['ADMIN']],
        'Editor': [PERMISSIONS['WRITE'], PERMISSIONS['UPLOAD'], PERMISSIONS['EDIT']],
        'Visitor': [PERMISSIONS['WRITE'], PERMISSIONS['UPLOAD']],
    },
    'DEFAULT': 'Visitor'
}

user_follow = db.Table('user_follows',
                       db.Column('user_id', db.Integer,
                                 db.ForeignKey('users.id')),
                       db.Column('follower_user_id', db.Integer,
                                 db.ForeignKey('users.id')),
                       )
post_tag = db.Table('post_tags',
                    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id')),
                    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'))
                    )
user_group = db.Table('user_groups',
                      db.Column('group_id', db.Integer,
                                db.ForeignKey('groups.id')),
                      db.Column('user_id', db.Integer,
                                db.ForeignKey('users.id'))
                      )

post_file = db.Table('post_files',
                     db.Column('file_id', db.Integer,
                               db.ForeignKey('files.id')),
                     db.Column('post_id', db.Integer,
                               db.ForeignKey('posts.id')),
                     )

project_creator = db.Table('project_creators',
                        db.Column('creator_user_id', db.Integer,
                                db.ForeignKey('users.id')),
                      db.Column('project_id', db.Integer,
                                db.ForeignKey('projects.id')),
                      )

phase_file = db.Table('phase_files',
                      db.Column('file_id', db.Integer,
                                db.ForeignKey('files.id')),
                      db.Column('phase_id', db.Integer,
                                db.ForeignKey('phases.id')),
                      )

phase_upload_file = db.Table('phase_upload_files',
                      db.Column('upload_file_id', db.Integer,
                                db.ForeignKey('files.id')),
                      db.Column('phase_id', db.Integer,
                                db.ForeignKey('phases.id')),
                      )

post_like = db.Table('post_likes',
                     db.Column('user_id', db.Integer,
                               db.ForeignKey('users.id')),
                     db.Column('post_id', db.Integer,
                               db.ForeignKey('posts.id')),
                     )

post_save = db.Table('post_saves',
                     db.Column('user_id', db.Integer,
                               db.ForeignKey('users.id')),
                     db.Column('post_id', db.Integer,
                               db.ForeignKey('posts.id')),
                     )
category_save = db.Table('category_saves',
                         db.Column('user_id', db.Integer,
                                   db.ForeignKey('users.id')),
                         db.Column('category_id', db.Integer,
                                   db.ForeignKey('categories.id')),
                         )
comment_agree = db.Table('comment_agrees',
                         db.Column('user_id', db.Integer,
                                   db.ForeignKey('users.id')),
                         db.Column('comment_id', db.Integer,
                                   db.ForeignKey('comments.id')),
                         )


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(64), unique=True)
    password = db.Column(db.String(128))
    sex = db.Column(db.Enum('male', 'female', 'unknown'),
                    server_default=("unknown"))
    email = db.Column(db.String(64), unique=True)
    phone = db.Column(db.String(32), unique=True)
    name = db.Column(db.String(64))
    title = db.Column(db.String(128))
    about_me = db.Column(db.Text())
    avatar_file_id = db.Column(db.Integer, db.ForeignKey('files.id'))
    # one-one: User.avatar-File.user
    avatar = db.relationship(
        'File', foreign_keys=avatar_file_id, backref='user', uselist=False)

    reg_date = db.Column(db.DateTime, default=datetime.utcnow)
    # one-many: User.role-Role.users
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    # many-many: User.groups-Group.users
    groups = db.relationship('Group', secondary=user_group,
                             lazy='subquery', backref=db.backref('users', lazy=True))
    # one-one: WxUser.user-User.wx_user
    wx_user = db.relationship('WxUser', backref='user', uselist=False)

    # one-many: Comment.author-User.comments
    comments = db.relationship(
        'Comment', backref=db.backref('author', lazy=True))
    # one-many: Post.author-User.posts
    posts = db.relationship('Post', backref=db.backref('author', lazy=True))

    # one-many: File.uploader-User.files
    files = db.relationship('File', foreign_keys='File.uploader_user_id',
                            backref=db.backref('uploader', lazy=True))

    # manay-many in same table:User.followed_users-User.follower_users
    followed_users = db.relationship('User',
                                     secondary=user_follow, lazy='subquery',
                                     primaryjoin=(user_follow.c.user_id == id),
                                     secondaryjoin=(
                                         user_follow.c.follower_user_id == id),
                                     backref=db.backref('follower_users', lazy=True))

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role_id is None:
            self.role_id = Role.query.filter_by(default=True).first().id

    def can(self, perm):
        return self.role is not None and self.role.has_permission(perm)

    def is_admin(self):
        return self.can(PERMISSIONS['ADMIN'])

    @staticmethod
    def create_admin():
        try:
            hashed_password = generate_password_hash(
                app.config['ADMIN_PASS'], method='sha256')
            new_user = User(
                login=app.config['ADMIN_LOGIN'],
                name=app.config['ADMIN_LOGIN'],
                password=hashed_password,
                role_id=1
            )
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            print(e)

    def __repr__(self):
        return '<User %r>' % self.login


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))
    default = db.Column(db.Boolean, default=False)
    permissions = db.Column(db.Integer)
    # one-many: role-Role.users
    users = db.relationship('User', backref=db.backref('role', lazy=True))

    def __init__(self, **kwargs):
        super(Role, self).__init__(**kwargs)
        if self.permissions is None:
            self.permissions = 0

    @staticmethod
    def insert_roles():
        roles = ROLE_PRESSENT['ROLES']
        default_role = ROLE_PRESSENT['DEFAULT']
        old_default = Role.query.filter_by(default=True).first()
        if old_default:
            old_default.default = False

        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.reset_permissions()
            for perm in roles[r]:
                role.add_permission(perm)
            role.default = (role.name == default_role)
            db.session.add(role)
            print(role)
        db.session.commit()

    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permissions(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm

    def __repr__(self):
        return '<Role %r>' % self.name


class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))

    def __repr__(self):
        return '<Group %r>' % self.name


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    # one-many: Post.author-User.posts
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # one-many: Post.category-Category.posts
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    show_comment = db.Column(db.Boolean, default=True)
    allow_comment = db.Column(db.Boolean, default=True)
    anonymity = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum('publish', 'draft', 'discard'),
                       server_default=("draft"))
    post_date = db.Column(db.DateTime, default=datetime.utcnow)
    publish_date = db.Column(db.DateTime)

    cover_img_url = db.Column(db.String(512))

    excerpt = db.Column(db.String(512))
    # one-many: Comment.parent_post-Post.comments
    comments = db.relationship(
        'Comment', backref=db.backref('parent_post', lazy=True))
    # many-many: Tag.posts-Post.tags
    tags = db.relationship('Tag', secondary=post_tag,
                           lazy='subquery', backref=db.backref('posts', lazy=True))
    # many-many: File.posts-Post.files
    files = db.relationship('File', secondary=post_file,
                            lazy='subquery', backref=db.backref('posts', lazy=True))
    # many-many: User.like_posts-Post.like_users
    like_users = db.relationship(
        'User', secondary=post_like, lazy='subquery', backref=db.backref('like_posts', lazy=True))
    # many-many: User.save_posts-Post.save_users
    save_users = db.relationship(
        'User', secondary=post_save, lazy='subquery', backref=db.backref('save_posts', lazy=True))

    def __repr__(self):
        return '<Post %r>' % self.title


class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))

    def __repr__(self):
        return '<Tag %r>' % self.name


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))

    # one-many: Post.category-Category.posts
    posts = db.relationship('Post', backref=db.backref('category', lazy=True))
    # many-many: Category.save_users-User.followed_categories
    save_users = db.relationship('User', secondary=category_save, lazy='subquery',
                                 backref=db.backref('followed_categories', lazy=True))

    def __repr__(self):
        return '<Category %r>' % self.name


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    # one-many: Comment.parent_post-Post.comments
    parent_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    # one-many: Comment.author-User.comments
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # mnay-many in same table: Comment.parent_comment-Comment.children_comments
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    anonymity = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum('publish', 'discard'),
                       server_default=("publish"))
    post_date = db.Column(db.DateTime, default=datetime.utcnow)

    # mnay-many in same table: Comment.parent_comment-Comment.children_comments
    children_comments = db.relationship('Comment', backref=db.backref(
        'parent_comment', lazy=True), remote_side=[id])
    # mnay-many: Comment.agree_users-User.agree_comments
    agree_users = db.relationship('User', secondary=comment_agree,
                                  lazy='subquery', backref=db.backref('agree_comments', lazy=True))

    def __repr__(self):
        return '<Comment %r>' % self.id


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    design = db.Column(db.Text)
    # one-many: Post.client-User.projects_as_client
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # many-many: User.projects-Project.creators
    creators = db.relationship('User', secondary=project_creator,
                            lazy='subquery', backref=db.backref('projects_as_creator', lazy=True))

    status = db.Column(db.Enum('draft','await', 'progress', 'delay', 'pending',
                               'abnormal', 'modify', 'finish', 'discard'), server_default=("draft"))
    post_date = db.Column(db.DateTime, default=datetime.utcnow)
    start_date = db.Column(db.DateTime)
    finish_date = db.Column(db.DateTime)
    last_pause_date = db.Column(db.DateTime)

    # one-many: project.client-User.projects_as_client
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref(
        'projects_as_client', lazy=True))
    # one-many: Comment.parent_post-Post.comments
    stages = db.relationship(
        'Stage', backref=db.backref('parent_project', lazy=True))
    current_stage_index = db.Column(db.Integer, default=0)

    # one-many: Propose.parent_project-Project.Proposes
    proposes = db.relationship(
        'Propose', backref=db.backref('parent_project', lazy=True))

    def __repr__(self):
        return '<Project %r>' % self.title


class Stage(db.Model):
    __tablename__ = 'stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    description = db.Column(db.String(512))
    # one-many: Project.stages-Stage.parent_project
    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    start_date = db.Column(db.DateTime)

    # one-many: Phase.parent_stage-Stage.phases
    phases = db.relationship(
        'Phase', backref=db.backref('parent_stage', lazy=True))

    def __repr__(self):
        return '<Stage %r>' % self.name


class Phase(db.Model):
    __tablename__ = 'phases'
    id = db.Column(db.Integer, primary_key=True)
    parent_stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'))
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
    

    # many-many: File.phases-Phase.files
    upload_files = db.relationship('File', secondary=phase_upload_file,
                            lazy='subquery', backref=db.backref('phases_as_upload', lazy=True))

    # many-many: File.phases-Phase.files
    files = db.relationship('File', secondary=phase_file,
                            lazy='subquery', backref=db.backref('phases', lazy=True))

    def __repr__(self):
        return '<Phase %r>' % self.id


class Propose(db.Model):
    __tablename__ = 'proposes'
    id = db.Column(db.Integer, primary_key=True)
    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    proposer_role = db.Column(
        db.Enum('creator', 'client'), server_default=("creator"))
    type = db.Column(db.Enum('postpone', 'overhaul'),
                     server_default=("postpone"))
    propose_date = db.Column(db.DateTime)

    def __repr__(self):
        return '<Phase %r>' % self.id


class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    # one-many: File.uploader-User.files
    uploader_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author=db.Column(db.String(64))
    name = db.Column(db.String(64))
    format = db.Column(db.String(16))
    url = db.Column(db.String(512), unique=True)
    from_url = db.Column(db.String(512))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    # one-many: Preview.file-File.previews
    previews = db.relationship(
        'Preview', backref=db.backref('file', lazy=True))
    description = db.Column(db.String(512))

    @staticmethod
    def clear_missing_file():
        files_list = File.query.all()
        for file in files_list:
            if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file.url)):
                for preview in file.previews:
                    db.session.delete(preview)
                db.session.delete(file)
        db.session.commit()

    def __repr__(self):
        return '<File %r>' % self.name


class Preview(db.Model):
    __tablename__ = 'previews'
    id = db.Column(db.Integer, primary_key=True)
    # one-many: Preview.file-File.previews
    bind_file_id = db.Column(db.Integer, db.ForeignKey('files.id'))
    url = db.Column(db.String(512), unique=True)
    size = db.Column(db.Integer)

    def __repr__(self):
        return '<Preview %r>' % self.nickname


class WxUser(db.Model):
    __tablename__ = 'wx_users'
    id = db.Column(db.Integer, primary_key=True)
    bind_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    openid = db.Column(db.String(128))
    nickname = db.Column(db.String(64))
    sex = db.Column(db.Integer)
    language = db.Column(db.String(32))
    city = db.Column(db.String(64))
    province = db.Column(db.String(64))
    country = db.Column(db.String(64))
    headimg_url = db.Column(db.String(512))
    unionid = db.Column(db.String(128))
    reg_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<WxUser %r>' % self.nickname


class Option(db.Model):
    __tablename__ = 'options'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    value = db.Column(db.String(512))

    def __repr__(self):
        return '<Option %r>' % self.name
