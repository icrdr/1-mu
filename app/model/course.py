from datetime import datetime, timedelta
from ..utility import generatePushUrl, generatePullUrl
from .. import db, scheduler, app
from .user import User, Group
import shortuuid
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdklive.request.v20161101.DescribeLiveStreamsOnlineListRequest import DescribeLiveStreamsOnlineListRequest
import json

# COURSE_TUTOR = db.Table(
#     'course_tutors',
#     db.Column('user_id', db.Integer,
#               db.ForeignKey('users.id')),
#     db.Column('course_id', db.Integer,
#               db.ForeignKey('courses.id')),
# )

# COURSE_MEMBER = db.Table(
#     'course_members',
#     db.Column('user_id', db.Integer,
#               db.ForeignKey('users.id')),
#     db.Column('course_id', db.Integer,
#               db.ForeignKey('courses.id')),
# )

# LIVEROOM_VIEWER = db.Table(
#     'live_room_viewers',
#     db.Column('user_id', db.Integer,
#               db.ForeignKey('users.id')),
#     db.Column('live_room_id', db.Integer,
#               db.ForeignKey('live_rooms.id')),
# )


# class Course(db.Model):
#     """Course Model"""
#     __tablename__ = 'courses'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(64))
#     excerpt = db.Column(db.String(512))
#     intro = db.Column(db.Text)
#     reg_date = db.Column(db.DateTime, default=datetime.utcnow)
#     # tutors = db.relationship('User', secondary=COURSE_TUTOR, lazy='subquery',
#     #                          backref=db.backref('courses_as_tutor', lazy=True))
#     # members = db.relationship('User', secondary=COURSE_MEMBER, lazy='subquery',
#     #                           backref=db.backref('courses_as_member', lazy=True))
#     live_room_id = db.Column(db.Integer, db.ForeignKey('live_rooms.id'))
#     live_room = db.relationship('LiveRoom', foreign_keys=live_room_id, backref=db.backref(
#         'live_room', lazy=True))

#     public = db.Column(db.Boolean, nullable=False, default=True)

#     def delete(self):
#         """Delete this Course."""
#         db.session.delete(self)
#         db.session.commit()

#     @staticmethod
#     def createCourse(name='a course', intro='<p>a course</p>', tutor_id=1):
#         """Create new a course."""
#         tutor = User.query.get(tutor_id)
#         if not tutor:
#             raise Exception("User is not exist!")

#         new_course = Course(
#             name=name,
#             intro=intro,
#         )
#         db.session.add(new_course)

#         new_live_room = LiveRoom()
#         db.session.add(new_live_room)

#         new_course.live_room = new_live_room
#         new_course.tutors.append(tutor)
#         new_course.members.append(tutor)

#         db.session.commit()
#         return new_course

#     def __repr__(self):
#         return '<Course id %s>' % self.id


class LiveRoom(db.Model):
    """LiveRoom Model"""
    __tablename__ = 'live_rooms'
    id = db.Column(db.Integer, primary_key=True)

    stream_url = db.Column(db.String(512))
    stream_auth = db.Column(db.String(512))
    rtmp_url = db.Column(db.String(512))
    flv_url = db.Column(db.String(512))
    hls_url = db.Column(db.String(512))
    url_exp_date = db.Column(db.DateTime, default=datetime.utcnow)
    streaming = db.Column(db.Boolean, nullable=False, default=False)
    current_host_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    current_host = db.relationship('User', foreign_keys=current_host_id, backref=db.backref(
        'live_rooms_as_current_host', lazy=True))
    # current_viewers = db.relationship('User', secondary=LIVEROOM_VIEWER,
    #                                   lazy='subquery', backref=db.backref('live_rooms_as_viewer', lazy=True))

    def doReady(self, host_id):
        host = User.query.get(host_id)
        if not host:
            raise Exception("User is not exist!")

        self.current_host_id = host_id

        if self.url_exp_date < datetime.utcnow():
            streamName = str(shortuuid.uuid())
            url, auth = generatePushUrl(streamName)
            rtmp_url, flv_url, hls_url = generatePullUrl(streamName)

            self.stream_url = url
            self.stream_auth = auth
            self.rtmp_url = rtmp_url
            self.flv_url = flv_url
            self.hls_url = hls_url
            self.url_exp_date = datetime.utcnow()+timedelta(hours=6)

        scheduler.add_job(
            check_stream,
            'interval',
            id='check_stream_' + str(self.id),
            args=[self.stream_auth.split('?')[0], self.id],
            seconds=3,
            replace_existing=True,  # not working
            misfire_grace_time=1,
            start_date=datetime.utcnow(),
            end_date=self.url_exp_date
        )
        print('start_checking_stream')

        db.session.commit()
        return self

    def doEnd(self):
        if scheduler.get_job('check_stream_' + str(self.id)):
            scheduler.remove_job('check_stream_' + str(self.id))
        self.current_host = None
        self.streaming = False
        print('abort_checking_steam;end_steam')
        db.session.commit()
        return self

    def __repr__(self):
        return '<LiveRoom id %s>' % self.id


# class LiveLog(db.Model):
#     """LiveLog Model"""
#     __tablename__ = 'live_logs'
#     id = db.Column(db.Integer, primary_key=True)
#     start_date = db.Column(db.DateTime)
#     end_date = db.Column(db.DateTime)

#     host_id = db.Column(db.Integer, db.ForeignKey('users.id'))
#     host = db.relationship('User', foreign_keys=host_id, backref=db.backref(
#         'live_log_as_host', lazy=True))

#     live_room_id = db.Column(db.Integer, db.ForeignKey('live_rooms.id'))
#     live_room = db.relationship('LiveRoom', foreign_keys=live_room_id, backref=db.backref(
#         'live_logs', lazy=True))

#     def __repr__(self):
#         return '<LiveLog id %s>' % self.id


def check_stream(streamName, live_room_id):
    client = AcsClient(
        app.config['ALIYUN_KEY'], app.config['ALIYUN_SECRET'], 'cn-shenzhen')

    request = DescribeLiveStreamsOnlineListRequest()
    request.set_accept_format('json')

    request.set_DomainName(app.config['LIVE_PUSH_HOST'])
    request.set_AppName(app.config['LIVE_APP_NAME'])
    request.set_StreamName(streamName)
    response = client.do_action_with_exception(request)
    res_json = json.loads(response)
    # print(res_json)
    print('check')
    if 'OnlineInfo' in res_json:
        online_info = res_json['OnlineInfo']
        if "LiveStreamOnlineInfo" in online_info:
            live_room = LiveRoom.query.get(live_room_id)
            if len(online_info['LiveStreamOnlineInfo']) > 0 and not live_room.streaming:
                live_room.streaming = True
                print('live room %d streaming: ON' % live_room_id)
            elif len(online_info['LiveStreamOnlineInfo']) == 0 and live_room.streaming:
                live_room.streaming = False
                print('live room %d streaming: OFF' % live_room_id)
            db.session.commit()
