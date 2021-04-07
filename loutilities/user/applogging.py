'''
applogging - define logging for the application
================================================
'''
# standard
import logging
from logging.handlers import SMTPHandler
from logging import Formatter
from logging.handlers import TimedRotatingFileHandler
from flask import current_app

# pypi
from flask_security import current_user

# homegrown

class UserFormatter(Formatter):
    # https://flask.palletsprojects.com/en/1.1.x/logging/#injecting-request-information
    def format(self, record):
        if current_user.is_authenticated:
            record.user_email = current_user.email
        else:
            record.user_email = 'anonymous'
        return super().format(record)

# ----------------------------------------------------------------------
def setlogging():
    # ----------------------------------------------------------------------

    # this is needed for any INFO or DEBUG logging
    current_app.logger.setLevel(logging.DEBUG)

    # uncomment next two lines to debug sqlalchemy pool usage
    # logging.basicConfig()
    # logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

    # # patch werkzeug logging -- not sure why this is being bypassed in werkzeug._internal._log
    # *** for some reason the following code caused debug pin not to be shown, see https://github.com/louking/rrwebapp/issues/300
    # werkzeug_logger = logging.getLogger('werkzeug')
    # werkzeug_logger.setLevel(logging.INFO)

    # set up logging
    ADMINS = current_app.config['EXCEPTION_EMAIL']
    application = current_app.config['APP_LOUTILITY']
    # to test, set if to True, and change run environment to production
    # if True:
    if not current_app.debug:
        if 'MAIL_SERVER' in current_app.config and 'MAIL_PORT' in current_app.config:
            mailhost = (current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        elif 'MAIL_SERVER' in current_app.config:
            mailhost = current_app.config['MAIL_SERVER']
        else:
            mailhost = 'localhost'
        mail_handler = SMTPHandler(mailhost,
                                   'noreply@steeplechasers.org',
                                   ADMINS, f'{application} exception encountered')
        if 'LOGGING_LEVEL_MAIL' in current_app.config:
            mailloglevel = current_app.config['LOGGING_LEVEL_MAIL']
        else:
            mailloglevel = logging.ERROR
        mail_handler.setLevel(mailloglevel)
        mail_handler.setFormatter(UserFormatter('''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s
User:               %(user_email)s

Message:

%(message)s
        '''))
        current_app.logger.addHandler(mail_handler)
        current_app.config['LOGGING_MAIL_HANDLER'] = mail_handler

        logpath = None
        if 'LOGGING_PATH' in current_app.config:
            logpath = current_app.config['LOGGING_PATH']

        if logpath:
            # file rotates every Monday
            file_handler = TimedRotatingFileHandler(logpath, when='W0', delay=True)
            if 'LOGGING_LEVEL_FILE' in current_app.config:
                fileloglevel = current_app.config['LOGGING_LEVEL_FILE']
            else:
                fileloglevel = logging.WARNING
            file_handler.setLevel(fileloglevel)
            current_app.logger.addHandler(file_handler)
            current_app.config['LOGGING_FILE_HANDLER'] = file_handler

            file_handler.setFormatter(UserFormatter(
                '%(asctime)s %(levelname)s: %(user_email)s %(message)s '
                '[in %(pathname)s:%(lineno)d]'
            ))


