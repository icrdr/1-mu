from flask import send_from_directory
from . import api, db, app

@app.errorhandler(404)
def page_not_found(e):
    return "404", 404

UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('../'+UPLOAD_FOLDER, filename)