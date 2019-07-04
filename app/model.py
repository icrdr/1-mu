from . import db, app
from datetime import datetime
import os

PERMISSIONS = {
        'ADMIN': 1,
        'WRITE': 2,
        'EDIT': 4,
        'UPLOAD': 8
    }

ROLE_PRESSENT = {
    'ROLES' : {
            'Visitor': [PERMISSIONS['WRITE'], PERMISSIONS['UPLOAD']],
            'Editor': [PERMISSIONS['WRITE'], PERMISSIONS['UPLOAD'], PERMISSIONS['EDIT']],
            'Admin': [PERMISSIONS['WRITE'], PERMISSIONS['EDIT'], PERMISSIONS['UPLOAD'],PERMISSIONS['ADMIN']],
        },
    'DEFAULT':'Visitor'
}

user_follow = db.Table('user_follows',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('follower_user_id', db.Integer, db.ForeignKey('users.id')),
)
post_tag = db.Table('post_tags',
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'))
)
user_group = db.Table('user_groups',
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'))
)
post_file = db.Table('post_files',
    db.Column('file_id', db.Integer, db.ForeignKey('files.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id')),
)

stage_file = db.Table('stage_files',
    db.Column('file_id', db.Integer, db.ForeignKey('files.id')),
    db.Column('stage_id', db.Integer, db.ForeignKey('stages.id')),
)

post_like = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id')),
)

post_save = db.Table('post_saves',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id')),
)
category_save = db.Table('category_saves',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id')),
)
comment_agree = db.Table('comment_agrees',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('comment_id', db.Integer, db.ForeignKey('comments.id')),
)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(64), unique=True, index=True)
    password = db.Column(db.String(128))

    email = db.Column(db.String(64), unique=True, index=True)
    phone = db.Column(db.String(32), unique=True, index=True)
    name = db.Column(db.String(64))
    title = db.Column(db.String(128))
    about_me = db.Column(db.Text())
    avatar_url = db.Column(db.String(256))
    reg_date = db.Column(db.DateTime, default=datetime.utcnow)
    # one-many: User.role-Role.users
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    # many-many: User.groups-Group.users
    groups = db.relationship('Group', secondary=user_group, lazy='subquery', backref=db.backref('users', lazy=True))
    # one-one: WxUser.user-User.wx_user
    wx_user = db.relationship('WxUser', backref='user', uselist=False)
    
    # one-many: Comment.author-User.comments
    comments = db.relationship('Comment', backref=db.backref('author', lazy=True))
    # one-many: Post.author-User.posts
    posts = db.relationship('Post', backref=db.backref('author', lazy=True))

    # one-many: File.uploader-User.files
    files = db.relationship('File', backref=db.backref('uploader', lazy=True))

    # manay-many in same table:User.followed_users-User.follower_users
    followed_users = db.relationship('User', 
        secondary=user_follow, lazy='subquery', 
        primaryjoin=(user_follow.c.user_id == id), 
        secondaryjoin=(user_follow.c.follower_user_id == id), 
        backref=db.backref('follower_users', lazy=True))
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role_id is None:
            self.role_id = Role.query.filter_by(default=True).first().id

    def can(self, perm):
        return self.role is not None and self.role.has_permission(perm)

    def is_admin(self):
        return self.can(PERMISSIONS['ADMIN'])

    def __repr__(self):
        return '<User %r>' % self.login

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(256))
    default = db.Column(db.Boolean, default=False, index=True)
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
    description = db.Column(db.String(256))

    def __repr__(self):
        return '<Group %r>' % self.name

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    content = db.Column(db.Text)
    # one-many: Post.author-User.posts
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # one-many: Post.category-Category.posts
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    allow_comment  = db.Column(db.Boolean, default=True)
    anonymity = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum('publish','draft','discard'), server_default=("draft"))
    public_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    cover_img_url = db.Column(db.String(256))

    excerpt = db.Column(db.String(256))
    # one-many: Comment.parent_post-Post.comments
    comments = db.relationship('Comment', backref=db.backref('parent_post', lazy=True))
    # many-many: Tag.posts-Post.tags
    tags = db.relationship('Tag', secondary=post_tag, lazy='subquery', backref=db.backref('posts', lazy=True))
    # many-many: File.posts-Post.files
    files = db.relationship('File', secondary=post_file, lazy='subquery', backref=db.backref('posts', lazy=True))
    # many-many: User.like_posts-Post.like_users
    like_users = db.relationship('User', secondary=post_like, lazy='subquery', backref=db.backref('like_posts', lazy=True))
    # many-many: User.save_posts-Post.save_users
    save_users = db.relationship('User', secondary=post_save, lazy='subquery', backref=db.backref('save_posts', lazy=True))

    def __repr__(self):
        return '<Post %r>' % self.title
    
class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(256))

    def __repr__(self):
        return '<Tag %r>' % self.name

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(256))

    # one-many: Post.category-Category.posts
    posts = db.relationship('Post', backref=db.backref('category', lazy=True))
    # many-many: Category.save_users-User.followed_categories
    save_users = db.relationship('User', secondary=category_save, lazy='subquery', backref=db.backref('followed_categories', lazy=True))
    
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
    status = db.Column(db.Enum('publish','discard'), server_default=("publish"), index=True)
    public_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # mnay-many in same table: Comment.parent_comment-Comment.children_comments
    children_comments = db.relationship('Comment', backref=db.backref('parent_comment', lazy=True), remote_side=[id])
    # mnay-many: Comment.agree_users-User.agree_comments
    agree_users = db.relationship('User', secondary=comment_agree, lazy='subquery', backref=db.backref('agree_comments', lazy=True))
    
    def __repr__(self):
        return '<Comment %r>' % self.id

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    design = db.Column(db.Text)
    # one-many: Post.client-User.projects_as_client
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # one-many: project.creator-User.projects_as_creator
    creator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.Enum('finish','progress','pending','delay','discard'), server_default=("pending"))
    public_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    start_date = db.Column(db.DateTime)

    # one-many: project.creator-User.projects_as_creator
    creator = db.relationship('User', foreign_keys=creator_user_id, backref=db.backref('projects_as_creator', lazy=True))
    # one-many: project.client-User.projects_as_client
    client = db.relationship('User', foreign_keys=client_user_id, backref=db.backref('projects_as_client', lazy=True))
    # one-many: Comment.parent_post-Post.comments
    stages = db.relationship('Stage', backref=db.backref('parent_project', lazy=True))
    def __repr__(self):
        return '<Project %r>' % self.title

class Stage(db.Model):
    __tablename__ = 'stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))

    # one-many: Post.client-User.projects_as_client
    parent_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))

    status = db.Column(db.Enum('finish','progress', 'modify', 'pending', 'delay', 'discard'), server_default=("pending"))
    start_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    deadline_date = db.Column(db.DateTime)

    # many-many: File.posts-Post.files
    files = db.relationship('File', secondary=stage_file, lazy='subquery', backref=db.backref('stages', lazy=True))

    def __repr__(self):
        return '<Project %r>' % self.title

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    # one-many: File.uploader-User.files
    uploader_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(64))
    format = db.Column(db.String(16))
    url = db.Column(db.String(256), unique=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    # one-many: Preview.file-File.previews
    previews = db.relationship('Preview', backref=db.backref('file', lazy=True))
    description = db.Column(db.String(256))

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
    url = db.Column(db.String(256), unique=True)
    def __repr__(self):
        return '<Preview %r>' % self.nickname

class WxUser(db.Model):
    __tablename__ = 'wx_users'
    id = db.Column(db.Integer, primary_key=True)
    bind_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    openid = db.Column(db.String(128))
    nickname = db.Column(db.String(64))
    sex = db.Column(db.Integer)
    language = db.Column(db.String(16))
    city = db.Column(db.String(32))
    province = db.Column(db.String(32))
    country = db.Column(db.String(32))
    headimg_url = db.Column(db.String(256))
    unionid = db.Column(db.String(128))
    reg_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    def __repr__(self):
        return '<WxUser %r>' % self.nickname

