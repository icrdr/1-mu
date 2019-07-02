from flask import send_from_directory
from . import db, app

@app.errorhandler(404)
def page_not_found(e):
    return "404", 404

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('../'+ app.config['UPLOAD_FOLDER'], filename)