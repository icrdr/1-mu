"""
User Role Group WxUser
"""

from datetime import datetime
from werkzeug.security import generate_password_hash
from .. import db, app

PERMISSIONS = app.config['PERMISSIONS']
ROLE_PRESSENT = app.config['ROLE_PRESSENT']

USER_FOLLOW = db.Table('user_follows',
                       db.Column('user_id', db.Integer,
                                 db.ForeignKey('users.id')),
                       db.Column('follower_user_id', db.Integer,
                                 db.ForeignKey('users.id')),
                       )
USER_GROUP = db.Table('user_groups',
                      db.Column('group_id', db.Integer,
                                db.ForeignKey('groups.id')),
                      db.Column('user_id', db.Integer,
                                db.ForeignKey('users.id'))
                      )

GROUP_ADMIN = db.Table('group_admins',
                      db.Column('user_id', db.Integer,
                                db.ForeignKey('users.id')),
                      db.Column('group_id', db.Integer,
                                db.ForeignKey('groups.id')),
                      )


class User(db.Model):
    """User Model"""
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
    groups = db.relationship('Group', secondary=USER_GROUP,
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
                                     secondary=USER_FOLLOW, lazy='subquery',
                                     primaryjoin=(USER_FOLLOW.c.user_id == id),
                                     secondaryjoin=(
                                         USER_FOLLOW.c.follower_user_id == id),
                                     backref=db.backref('follower_users', lazy=True))

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role_id is None:
            self.role_id = Role.query.filter_by(default=True).first().id

    def can(self, perm):
        """Check user's role has particular permission."""
        return self.role is not None and self.role.has_permission(perm)

    def is_admin(self):
        """Check if user is admin or not"""
        return self.can(PERMISSIONS['ADMIN'])

    @staticmethod
    def create_admin():
        """Create server's admin user. Call it on server's initiation."""
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

    def __repr__(self):
        return '<User %r>' % self.login


class Role(db.Model):
    """Role Model"""
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
        """Generate roles from config. Call it on server's initiation."""
        roles = ROLE_PRESSENT['ROLES']
        default_role = ROLE_PRESSENT['DEFAULT']
        old_default = Role.query.filter_by(default=True).first()
        if old_default:
            old_default.default = False

        for _r in roles:
            role = Role.query.filter_by(name=_r).first()
            if role is None:
                role = Role(name=_r)
            role.reset_permissions()
            for perm in roles[_r]:
                role.add_permission(perm)
            role.default = (role.name == default_role)
            db.session.add(role)
            print(role)
        db.session.commit()

    def add_permission(self, perm):
        """Adding particular permission to this role."""
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        """Removing particular permission to this role."""
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permissions(self):
        """Clear this role's permissions."""
        self.permissions = 0

    def has_permission(self, perm):
        """Check if this role has particular permission."""
        return self.permissions & perm == perm

    def __repr__(self):
        return '<Role %r>' % self.name


class Group(db.Model):
    """Group Model"""
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))
    admins = db.relationship(
        'User', secondary=GROUP_ADMIN,
        lazy='subquery', backref=db.backref('groups_as_admin', lazy=True))
    reg_date = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return '<Group %r>' % self.name


class WxUser(db.Model):
    """WxUser Model"""
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
