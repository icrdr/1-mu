from flask_restplus import Resource, reqparse, fields
from .. import api, db, app
from werkzeug import utils, datastructures
import os

ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

media = api.namespace('api/media', description='upload operations')

@media.route('/')
class Upload(Resource):
    def post(self):
        upload_parser = reqparse.RequestParser()
        upload_parser.add_argument('file', type=datastructures.FileStorage, location='files')
        args = upload_parser.parse_args()
        file = args['file']

        if file and allowed_file(file.filename):
            filename = utils.secure_filename(file.filename)
            file.save(UPLOAD_FOLDER + filename)
            return {'emg': 's!'}
        else:
            return {'emg': 'f!'}