from datetime import datetime, timedelta
from ..utility import generatePushUrl, generatePullUrl
from .. import db, scheduler, app
from .user import User, Group

LIVEROOM_HOST = db.Table(
    'live_room_hosts',
    db.Column('user_id', db.Integer,
              db.ForeignKey('users.id')),
    db.Column('live_room_id', db.Integer,
              db.ForeignKey('live_rooms.id')),
)

LIVEROOM_ADMIN = db.Table(
    'live_room_admins',
    db.Column('user_id', db.Integer,
              db.ForeignKey('users.id')),
    db.Column('live_room_id', db.Integer,
              db.ForeignKey('live_rooms.id')),
)

LIVEROOM_USER = db.Table(
    'live_room_members',
    db.Column('user_id', db.Integer,
              db.ForeignKey('users.id')),
    db.Column('live_room_id', db.Integer,
              db.ForeignKey('live_rooms.id')),
)

LIVEROOM_VIEWER = db.Table(
    'live_room_viewers',
    db.Column('user_id', db.Integer,
              db.ForeignKey('users.id')),
    db.Column('live_room_id', db.Integer,
              db.ForeignKey('live_rooms.id')),
)


class LiveRoom(db.Model):
    """LiveRoom Model"""
    __tablename__ = 'live_rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    description = db.Column(db.String(512))
    reg_date = db.Column(db.DateTime, default=datetime.utcnow)
    hosts = db.relationship('User', secondary=LIVEROOM_HOST, lazy='subquery',
                            backref=db.backref('live_rooms_as_host', lazy=True))
    admins = db.relationship('User', secondary=LIVEROOM_ADMIN, lazy='subquery',
                             backref=db.backref('live_rooms_as_admin', lazy=True))
    members = db.relationship('User', secondary=LIVEROOM_USER, lazy='subquery',
                              backref=db.backref('live_rooms_as_member', lazy=True))

    public = db.Column(db.Boolean, nullable=False, default=True)
    steam_url = db.Column(db.String(512))
    steam_auth = db.Column(db.String(512))
    rtmp_url = db.Column(db.String(512))
    flv_url = db.Column(db.String(512))
    hls_url = db.Column(db.String(512))
    url_exp_date = db.Column(db.DateTime, default=datetime.utcnow)
    current_host_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    current_host = db.relationship('User', foreign_keys=current_host_id, backref=db.backref(
        'live_rooms_as_current_host', lazy=True))
    current_viewers = db.relationship('User', secondary=LIVEROOM_VIEWER,
                                      lazy='subquery', backref=db.backref('live_rooms_as_viewer', lazy=True))

    def delete(self):
        """Delete this LiveRoom."""
        db.session.delete(self)
        db.session.commit()

    def doReady(self, host_id):
        host = User.query.get(host_id)
        if not host:
            raise Exception("User is not exist!")
        elif not host in self.hosts:
            raise Exception("User is not this room's host!")

        if self.url_exp_date < datetime.utcnow():
            url, auth = generatePushUrl()
            rtmp_url, flv_url, hls_url = generatePullUrl()

            self.steam_url = url
            self.steam_auth = auth
            self.rtmp_url = rtmp_url
            self.flv_url = flv_url
            self.hls_url = hls_url
            self.url_exp_date = datetime.utcnow()+timedelta(hours=6)

        self.current_host_id = host_id
        db.session.commit()

        return self

    @staticmethod
    def createLiveRoom(name='live room', description='a live room', host_id=1):
        """Create new room."""
        host = User.query.get(host_id)
        if not host:
            raise Exception("User is not exist!")

        new_room = LiveRoom(
            name=name,
            description=description,
        )

        db.session.add(new_room)
        new_room.hosts.append(host)

        db.session.commit()
        return new_room

    def __repr__(self):
        return '<LiveRoom id %s>' % self.id


class LiveLog(db.Model):
    """LiveLog Model"""
    __tablename__ = 'live_logs'
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    host_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    host = db.relationship('User', foreign_keys=host_id, backref=db.backref(
        'live_log_as_host', lazy=True))

    live_room_id = db.Column(db.Integer, db.ForeignKey('live_rooms.id'))
    live_room = db.relationship('LiveRoom', foreign_keys=live_room_id, backref=db.backref(
        'live_logs', lazy=True))

    def __repr__(self):
        return '<LiveLog id %s>' % self.id
