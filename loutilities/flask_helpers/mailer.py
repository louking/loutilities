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
def sendmail(subject, fromaddr, toaddr, html, text='', ccaddr=None, replytoaddr=None):
#----------------------------------------------------------------------
    '''
    send mail

    :param subject: subject of email
    :param fromaddr: from address to use
    :param toaddr: to address to use, may be list of addresses or comma separated
    :param html: html to send
    :param text: optional text alternative to send
    :param ccaddr: optional cc address to use, may be list of addresses or comma separated
    :param replytoaddr: optional reply_to address to use, may be list of addresses or comma separated
    :returns: response from flask_mail.send
    '''
    current_app.logger.info('sendmail(): from={}, to={}, cc={}, subject="{}"'.format(fromaddr, toaddr, ccaddr, subject))

    # get current app's mailer
    mail = current_app.extensions.get('mail')

    message = Message(
        sender=fromaddr,
        recipients=toaddr if isinstance(toaddr, list) else [a.strip() for a in toaddr.split(',')],
        cc=ccaddr if not ccaddr or isinstance(ccaddr, list) else [a.strip() for a in ccaddr.split(',')],
        reply_to=replytoaddr if not replytoaddr or isinstance(replytoaddr, list) else [a.strip() for a in replytoaddr.split(',')],
        subject=subject,
        html=html,
        body=text,
    )

    mail.send(message)

    if debug: current_app.logger.debug('sendmail(): message.html={}'.format(message.html))
