from .. import db


class Option(db.Model):
    __tablename__ = 'options'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    value = db.Column(db.String(512))

    @staticmethod
    def init_option():
        new_option = Option(
            name='allow_sign_in',
            value=1
        )

        db.session.add(new_option)
        db.session.commit()

    def __repr__(self):
        return '<Option %r>' % self.name
