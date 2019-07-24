from .. import db

class Option(db.Model):
    __tablename__ = 'options'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    value = db.Column(db.String(512))

    def __repr__(self):
        return '<Option %r>' % self.name