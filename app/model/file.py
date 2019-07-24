from .. import db, app
from datetime import datetime
import os

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    # one-many: File.uploader-User.files
    uploader_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.Column(db.String(64))
    name = db.Column(db.String(64))
    format = db.Column(db.String(16))
    url = db.Column(db.String(512), unique=True)
    from_url = db.Column(db.String(512))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    # one-many: Preview.file-File.previews
    previews = db.relationship(
        'Preview', backref=db.backref('file', lazy=True))
    description = db.Column(db.String(512))

    @staticmethod
    def clear_missing_file():
        files_list = File.query.all()
        for file in files_list:
            if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file.url)):
                for preview in file.previews:
                    db.session.delete(preview)
                db.session.delete(file)
        db.session.commit()

    def __repr__(self):
        return '<File %r>' % self.name

class Preview(db.Model):
    __tablename__ = 'previews'
    id = db.Column(db.Integer, primary_key=True)
    # one-many: Preview.file-File.previews
    bind_file_id = db.Column(db.Integer, db.ForeignKey('files.id'))
    url = db.Column(db.String(512), unique=True)
    size = db.Column(db.Integer)

    def __repr__(self):
        return '<Preview %r>' % self.nickname