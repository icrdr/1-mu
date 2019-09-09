"""
User Role Group WxUser
"""

from datetime import datetime
from werkzeug.security import generate_password_hash
from .. import db, app
import shortuuid
from .misc import Option

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

    def delete(self):
        if self.wx_user:
            db.session.delete(self.wx_user)
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def create_admin():
        """Create server's admin user. Call it on server's initiation."""
        admin = User.create_user(
            login=app.config['ADMIN_LOGIN'],
            password=app.config['ADMIN_PASS'],
            role_id=1
        )
        return admin

    @staticmethod
    def create_user(login=str(shortuuid.uuid()), password=str(shortuuid.uuid()), name='', role_id=3, email='', phone='', sex='unknown'):
        option = Option.query.filter_by(name='allow_sign_in').first()
        if option.value == '0':
            raise Exception('Registration closed')

        if not name:
            name = login

        new_user = User(
            login=login,
            name=name,
            password=generate_password_hash(
                password, method='sha256'),
            role_id=role_id,
            email=email,
            phone=phone,
            sex=sex
        )

        db.session.add(new_user)
        db.session.commit()
        return new_user

    def __repr__(self):
        return '<User %r>' % self.login


class Role(db.Model):
    """Role Model"""
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))
    default = db.Column(db.Boolean, nullable=False, default=False)
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

    def delete(self):
        """Delte this project."""
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def create_group(name, description, admin_id, user_id):
        """Create new group."""
        # create project
        new_group = Group(
            name=name,
            description=description
        )
        db.session.add(new_group)

        for _id in admin_id:
            new_group.admins.append(User.query.get(_id))
        for _id in user_id:
            new_group.users.append(User.query.get(_id))

        db.session.commit()
        return new_group

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

    @staticmethod
    def create_wx_user(data):
        option = Option.query.filter_by(name='allow_sign_in').first()
        if option.value == '0':
            raise Exception('Registration closed')

        new_wx_user = WxUser(
            openid=data['openid'],
            nickname=data['nickname'],
            sex=data['sex'],
            language=data['language'],
            city=data['city'],
            province=data['province'],
            country=data['country'],
            headimg_url=data['headimgurl'],
            unionid=data['unionid']
        )
        db.session.add(new_wx_user)
        # create a new account on our serves and bind it to the wechat account.

        new_user = User(
            login=str(shortuuid.uuid()),
            name=data['nickname'],
            password=generate_password_hash(
                str(shortuuid.uuid()), method='sha256'),
            wx_user=new_wx_user
        )

        db.session.add(new_user)
        sex = 'unknown'
        if data['sex'] == 1:
            sex = 'male'
        elif data['sex'] == 2:
            sex = 'female'
        new_user.sex = sex

        db.session.commit()
        return new_wx_user

    def __repr__(self):
        return '<WxUser %r>' % self.nickname

class Message(db.Model):
    """Message Model"""
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    send_date = db.Column(db.DateTime, default=datetime.utcnow)
    read_date = db.Column(db.DateTime)

    content = db.Column(db.Text)
    read = db.Column(db.Boolean, nullable=False, default=False)

    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    from_user = db.relationship('User', foreign_keys=from_user_id, backref=db.backref(
        'messages_as_sender', lazy=True))

    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    to_user = db.relationship('User', foreign_keys=to_user_id, backref=db.backref(
        'messages_as_receiver', lazy=True))

    def __repr__(self):
        return '<Message %r>' % self.id