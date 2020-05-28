'''
mailer - send email
================================================
'''
# standard

# pypi
from flask import current_app
from flask_mail import Message

debug = False

#----------------------------------------------------------------------
def sendmail(subject, fromaddr, toaddr, html, text='', ccaddr=None ):
#----------------------------------------------------------------------
    '''
    send mail

    :param subject: subject of email
    :param fromaddr: from address to use
    :param toaddr: to address to use, may be list of addresses
    :param html: html to send
    :param text: optional text alternative to send
    :returns: response from flask_mail.send
    '''
    current_app.logger.info('sendmail(): from={}, to={}, cc={}, subject="{}"'.format(fromaddr, toaddr, ccaddr, subject))

    # get current app's mailer
    mail = current_app.extensions.get('mail')

    message = Message(
        sender=fromaddr,
        recipients=toaddr if isinstance(toaddr, list) else [toaddr],
        subject=subject,
        html=html,
        body=text,
    )

    mail.send(message)

    if debug: current_app.logger.debug('sendmail(): message.html={}'.format(message.html))
