from flask import send_from_directory, make_response
from . import db, app

@app.errorhandler(404)
def page_not_found(e):
    return "404", 404

@app.route('/'+app.config['UPLOAD_FOLDER']+'<path:filename>')
def uploaded_file(filename):
    return send_from_directory('../'+ app.config['UPLOAD_FOLDER'], filename)

@app.route('/'+app.config['DOWNLOAD_FOLDER']+'<path:filename>')
def downlod_file(filename):
    return send_from_directory('../'+ app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)