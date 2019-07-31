from .. import db, app
from datetime import datetime
import os
import shortuuid
from psd_tools import PSDImage
from PIL import Image
from .post import Tag

FILE_TAG = db.Table(
    'file_tags',
    db.Column('tag_id', db.Integer,
              db.ForeignKey('tags.id')),
    db.Column('file_id', db.Integer,
              db.ForeignKey('files.id')),
)

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
    public = db.Column(db.Boolean, default=False)
    tags = db.relationship(
        'Tag', secondary=FILE_TAG,
        lazy='subquery', backref=db.backref('files', lazy=True))

    @staticmethod
    def create_file(uploader_id, file, tags, public):
        # filename = utils.secure_filename(file.filename)
        format = file.filename.split(".")[-1]
        rawname = file.filename[:-len(format)-1]

        date = datetime.utcnow().strftime("%Y%m%d")
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        random_name = str(shortuuid.uuid())
        filename = random_name +'.'+ format
        path = os.path.join(app.config['UPLOAD_FOLDER'], year, month, day)

        if not os.path.exists(path):
            os.makedirs(path)

        file.save(os.path.join(path, filename))
        
        new_file = File(
            uploader_user_id = uploader_id,
            name = rawname,
            format = format,
            url = str(os.path.join(year, month, day , filename)).replace('\\', '/')
        )

        if public:
            new_file.public = True
        
        if tags:
            for tag in tags:
                _tag = Tag.query.filter_by(name=tag).first()
                if not _tag:
                    _tag = Tag(name=tag)
                    db.session.add(_tag)
                new_file.tags.append(_tag)

        db.session.add(new_file)
        db.session.commit()

        if format in ['png','jpg','psd','jpeg','gif','bmp','tga','tiff','tif']:
            try:
                im_path = os.path.join(path, filename)
                im = Image.open(im_path)
                im = im.convert('RGB')
                for size in app.config['THUMBNAIL_SIZE']:
                    im.thumbnail((size, size))
                    im.save(os.path.join(path, random_name) + "_%s.jpg"%str(size), "JPEG")

                    new_preview = Preview(
                        bind_file_id = new_file.id,
                        url = str(os.path.join(year, month, day , random_name+"_%s.jpg"%str(size))).replace('\\', '/'),
                        size = size
                    )
                    db.session.add(new_preview)

                db.session.commit()
            except Exception as e:
                print(e)

        return new_file

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