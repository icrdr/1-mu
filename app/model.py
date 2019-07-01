from . import db
from datetime import datetime

PERMISSIONS = {
        'ADMIN': 1,
        'WRITE': 2
    }

ROLE_PRESSENT = {
    'ROLES' : {
            'Visitor': [],
            'Editor': [PERMISSIONS['WRITE']],
            'Admin': [PERMISSIONS['WRITE'], PERMISSIONS['ADMIN']],
        },
    'DEFAULT':'Visitor'
}

user_follow = db.Table('user_follows',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('follower_user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('follow_date', db.DateTime, default=datetime.utcnow)
)
post_tag = db.Table('post_tags',
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'))
)

post_like = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id')),
    db.Column('like_date', db.DateTime, default=datetime.utcnow)
)

post_save = db.Table('post_saves',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id')),
    db.Column('save_date', db.DateTime, default=datetime.utcnow)
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
    avatar_url = db.Column(db.String(128))
    reg_date = db.Column(db.DateTime, default=datetime.utcnow)
    # one-many: User.role-Role.users
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    # one-many: Post.author-User.posts
    posts = db.relationship('Post', backref=db.backref('author', lazy=True))
    # one-many: Comment.author-User.comments
    comments = db.relationship('Comment', backref=db.backref('author', lazy=True))
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
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(120))
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

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80))
    content = db.Column(db.Text)
    # one-many: Post.author-User.posts
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # one-many: Post.category-Category.posts
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    allow_comment  = db.Column(db.Boolean, default=True)
    anonymity = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum('publish','draft','discard'), server_default=("draft"))
    public_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    excerpt = db.Column(db.String(120))
    # one-many: Comment.parent_post-Post.comments
    comments = db.relationship('Comment', backref=db.backref('parent_post', lazy=True))
    # many-many: Tag.posts-Post.tags
    tags = db.relationship('Tag', secondary=post_tag, lazy='subquery', backref=db.backref('posts', lazy=True))
    # many-many: User.like_posts-Post.like_users
    like_users = db.relationship('User', secondary=post_like, lazy='subquery', backref=db.backref('like_posts', lazy=True))
    # many-many: User.save_posts-Post.save_users
    save_users = db.relationship('User', secondary=post_save, lazy='subquery', backref=db.backref('save_posts', lazy=True))

    def __repr__(self):
        return '<Post %r>' % self.title
    
class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True)
    description = db.Column(db.String(120))

    def __repr__(self):
        return '<Tag %r>' % self.name

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True)
    description = db.Column(db.String(120))

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


class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    # one-many: File.uploader-User.files
    uploader_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(40))
    format = db.Column(db.String(20))
    url = db.Column(db.String(120), unique=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    description = db.Column(db.String(120))

    def __repr__(self):
        return '<File %r>' % self.name