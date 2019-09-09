from .. import db
from datetime import datetime

post_tag = db.Table('post_tags',
                    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id')),
                    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'))
                    )


post_file = db.Table('post_files',
                     db.Column('file_id', db.Integer,
                               db.ForeignKey('files.id')),
                     db.Column('post_id', db.Integer,
                               db.ForeignKey('posts.id')),
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

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    # one-many: Post.author-User.posts
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # one-many: Post.category-Category.posts
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    show_comment = db.Column(db.Boolean, nullable=False, default=True)
    allow_comment = db.Column(db.Boolean, nullable=False, default=True)
    anonymity = db.Column(db.Boolean, nullable=False, default=False)
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
    anonymity = db.Column(db.Boolean, nullable=False, default=False)
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
class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(512))

    def __repr__(self):
        return '<Tag %r>' % self.name