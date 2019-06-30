from . import db
from datetime import datetime

user_follow = db.Table('user_follow',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('follower_user_id', db.Integer, db.ForeignKey('user.id'))
)
post_tag = db.Table('post_tag',
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)

post_like = db.Table('post_like',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)

post_save = db.Table('post_save',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)
category_save = db.Table('category_save',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'))
)
comment_agree = db.Table('comment_agree',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('comment_id', db.Integer, db.ForeignKey('comment.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(50), unique=True, nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)

    email = db.Column(db.String(80), unique=True)
    phone = db.Column(db.String(30), unique=True)
    name = db.Column(db.String(50))
    title = db.Column(db.String(80))
    avatar_url = db.Column(db.String(120))
    reg_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # one-many: User.role-Role.users
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False, default=2)

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
    

    def __repr__(self):
        return '<User %r>' % self.login

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(120))
    # one-many: role-Role.users
    users = db.relationship('User', backref=db.backref('role', lazy=True))

    def __repr__(self):
        return '<Role %r>' % self.name

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # one-many: Post.author-User.posts
    author_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # one-many: Post.category-Category.posts
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    allow_comment  = db.Column(db.Boolean, nullable=False, default=True)
    anonymity = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.Enum('publish','draft','discard'), nullable=False, server_default=("draft"))
    public_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(120))

    def __repr__(self):
        return '<Tag %r>' % self.name

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(120))

    # one-many: Post.category-Category.posts
    posts = db.relationship('Post', backref=db.backref('category', lazy=True))
    # many-many: Category.save_users-User.followed_categories
    save_users = db.relationship('User', secondary=category_save, lazy='subquery', backref=db.backref('followed_categories', lazy=True))
    
    def __repr__(self):
        return '<Category %r>' % self.name

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    # one-many: Comment.parent_post-Post.comments
    parent_post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    # one-many: Comment.author-User.comments
    author_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # mnay-many in same table: Comment.parent_comment-Comment.children_comments
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    anonymity = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.Enum('publish','discard'), nullable=False, server_default=("publish"))
    public_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # mnay-many in same table: Comment.parent_comment-Comment.children_comments
    children_comments = db.relationship('Comment', backref=db.backref('parent_comment', lazy=True), remote_side=[id])
    # mnay-many: Comment.agree_users-User.agree_comments
    agree_users = db.relationship('User', secondary=comment_agree, lazy='subquery', backref=db.backref('agree_comments', lazy=True))
    
    def __repr__(self):
        return '<Comment %r>' % self.id


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # one-many: File.uploader-User.files
    uploader_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(40), unique=True, nullable=False)
    format = db.Column(db.String(20), unique=True, nullable=False)
    url = db.Column(db.String(120), unique=True, nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    description = db.Column(db.String(120))

    def __repr__(self):
        return '<File %r>' % self.name