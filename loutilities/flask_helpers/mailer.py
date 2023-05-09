'''
mailer - send email
================================================
'''
# standard

# pypi
from flask import current_app
from flask_mail import Message
import mimetypes

debug = False

#----------------------------------------------------------------------
def sendmail(subject, fromaddr, toaddr, html, text='', ccaddr=None, replytoaddr=None, attachments=[]):
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
    :param attachments: optional attachments to include, list of Dict containing {'filename': 'text-name', 'data': 'file-data'}
    :returns: response from flask_mail.send
    '''
    stubbed = current_app.config.get('MAIL_SUPPRESS_SEND', current_app.config.get('TESTING', False))
    stubbed_txt = '[STUBBED] ' if stubbed else ''
    current_app.logger.info(f'{stubbed_txt}sendmail(): from={fromaddr}, to={toaddr}, cc={ccaddr}, subject="{subject}"')

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

    for attachment in attachments:
        if all(k in attachment for k in ("filename","data")):
            message.attach(attachment['filename'], mimetypes.guess_type(attachment['filename'])[0],attachment['data']);
 
    mail.send(message)

    if debug: current_app.logger.debug('sendmail(): message.html={}'.format(message.html))
