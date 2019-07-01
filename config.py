import os
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # link to mysql
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    # offical tell me to set to true
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    # enabling chinese char
    RESTFUL_JSON = dict(ensure_ascii=False)

    # about upload
    UPLOAD_FOLDER = 'uploads/'
    ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024

    # RequestParser error https://flask-restplus.readthedocs.io/en/stable/parsing.html
    BUNDLE_ERRORS = True
    # disable fields mask https://flask-restplus.readthedocs.io/en/stable/mask.html
    RESTPLUS_MASK_SWAGGER = False
    # validation fields or args https://flask-restplus.readthedocs.io/en/stable/swagger.html
    RESTPLUS_VALIDATE = True

    PERMISSIONS = {
        'ADMIN': 1,
        'WRITE': 2
    }

    ROLE_PRESSENT = {
        'ROLES' : {
                'Visitor': [],
                'Editor': [PERMISSIONS['WRITE']],
                'Admin': [PERMISSIONS['WRITE'], PERMISSIONS['ADMIN']],
            },
        'DEFAULT':'Visitor'
    }

class DevelopmentConfig(Config):
    pass

class TestingConfig(Config):
    pass

class ProductionConfig(Config):
    pass

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}