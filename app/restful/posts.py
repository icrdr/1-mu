from flask_restplus import Resource, reqparse, fields
from .. import api, db
from ..model import Post, User, Tag

n_post = api.namespace('api/posts', description='posts operations')

m_tag = api.model('tag', {
    'id': fields.Integer,
})

m_user = api.model('user', {
    'id': fields.Integer,
    'username': fields.String,
})

m_post = api.model('post', {
    'id': fields.Integer(readOnly=True, description='The user unique identifier'),
    'title': fields.String(required=True, description='The user name'),
    'author': fields.Nested(m_user),
    'tags':fields.List(fields.Nested(m_tag))
})

@n_post.route('/')
@api.doc(params={'id': 'An ID'})
class PostList(Resource):
    @api.marshal_with(m_post, envelope='posts')
    def get(self):
        get_parser = reqparse.RequestParser()
        get_parser.add_argument('post_id', action='split', location='args')
        args = get_parser.parse_args()
        if args['post_id']:
            # post = Post.query.filter(Post.id.in_(args['post_id'])).all()
            post = Post.query.filter(Post.author.has(User.id.in_(args['post_id']))).all()
            if post:
                print(post)
                return post
            else:
                api.abort(404, "user {} doesn't exist".format(args['post_id']))
        else:
            post_list = Post.query.all()
            if(post_list):
                return post_list
            else:
                api.abort(404, "user {} doesn't exist".format(args['post_id']))

    def delete(self):
        delete_parser = reqparse.RequestParser()
        delete_parser.add_argument('post_id', required=True)
        args = delete_parser.parse_args()
        post = Post.query.filter_by(id=args['post_id']).first()
        if post:
            db.session.delete(post)
            db.session.commit()
            return {'ok': 'ok'}
        else:
            return {'error': 'post not exist'}
            
    @api.marshal_with(m_post)
    def post(self):
        post_parser = reqparse.RequestParser()
        post_parser.add_argument('title', required=True)
        post_parser.add_argument('body', required=True)
        post_parser.add_argument('tag_ids', action='append')
        post_parser.add_argument('user_id', type=int, required=True)
        args = post_parser.parse_args()
        author = User.query.filter_by(id=args['user_id']).first()
        if author:
            new_post = Post(title=args['title'], body=args['body'], user_id=args['user_id'])
            db.session.add(new_post)
            if args['tag_ids']:
                for t_id in args['tag_ids']:
                    tag = Tag.query.filter_by(id=t_id).first()
                    if tag:
                        new_post.tags.append(tag)
                    else:
                        return {'error': 'tag not exist'}
            db.session.commit()
            return new_post
        else:
            return {'error': 'user not exist'}