import smtplib
import subprocess
import time
from prefect import task
import pendulum as plm
from .utilities import get_logger

class NotifyError(Exception):
    def __init__(self, message):
        self.message = message

class Notification(object):
    def __init__(self, config):
        self.notifications = {}

    def submit(self, recipient, message):
        if recipient not in self.notifications:
            self.notifications[recipient] = []
        self.notifications[recipient].append(message)

    def notify_all(self):
        for recip in self.notifications:
            if len(self.notifications[recip]) > 0:
                self.notify(recip, '\r\n\r\n-------------------\r\n\r\n'.join(self.notifications[recip]))
                time.sleep(5)
            self.notifications[recip] = []

    def notify(self, recipient, message):
        raise NotImplementedError('Need to subclass Notification')

    def connect(self):
        raise NotImplementedError('Need to subclass Notification')

    def close(self):
        raise NotImplementedError('Need to subclass Notification')


class SendMail(Notification):
    def __init__(self, config):
        super().__init__(config)
        self.address = config.sendmail.address
        self.contact_info = config.sendmail.contact_info
        self.message_template = '\r\n'.join(['From: '+self.address,
                                  'To: {}',
                                  'Subject: [Rudaux] Notifications',
                                  '',
                                  'Greetings Human {},',
                                  '',
                                  '{}'
                                  '',
                                  '',
                                  'Beep boop,',
                                  'Rudaux Bot'])

    def notify(self, recipient, message):
        # -i flag: do NOT treat bare dot as EOF
        cmd = ['/usr/sbin/sendmail', f'-f {self.address}', self.contact_info[recipient]['address']]
        msg = self.message_template.format(self.contact_info[recipient]['address'], self.contact_info[recipient]['name'], message)
        proc = subprocess.Popen(cmd, shell=False,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate(input=msg.encode('utf-8'))
        #TODO handle errors
        #print(f"ret: {proc.returncode}")
        #print("stdout:" + str(out))
        #print("stderr:" + str(err))

    def connect(self):
        pass

    def close(self):
        pass


def validate_config(config):
    pass

@task(checkpoint=False)
def notify(config, grading_notifications, posting_notifications):
    logger = get_logger()
    sm = SendMail(config)
    flat_posting_notifications = list(set([item for sublist in posting_notifications for item in sublist]))
    if len(flat_posting_notifications)>0:
        logger.info(f"There are grades to post. Creating notification for instructor user ({config.instructor_user})")
        msg = '\r\n'.join(['You have grades to post!', '-------------------'] + [ f"{note[0]}: {note[1]}" for note in flat_posting_notifications])
        sm.submit(config.instructor_user, msg)
    for notification_set in grading_notifications:
        for grader in notification_set:
            for grd in notification_set[grader]:
                logger.info(f"TA user {grader} has {notification_set[grader][grd]['count']} left to grade for assignment {notification_set[grader][grd]['assignment']} in account {grd}.")
                msg = '\r\n'.join([ f"Grading Assignment---" +
                                    f"Account: {grd} -- "+
                                    f"Assignment: {notification_set[grader][grd]['assignment']} -- "+
                                    f"# Remaining to Grade: {notification_set[grader][grd]['count']}" for grd in notification_set[grader]])
                sm.submit(grader, msg)
    if plm.now().in_timezone(config.notify_timezone).format('dddd') in config.notify_days:
        logger.info(f"Today ({plm.now().in_timezone(config.notify_timezone).format('dddd')}) is a notification day; sending emails")
        sm.notify_all()

#class SMTP(Notification):
#    def __init__(self, config):
#        super().__init__(config)
#        self.hostname = config.smtp.hostname
#        self.username = config.smtp.username
#        self.passwd = config.smtp.passwd
#        self.address = config.smtp.address
#        self.contact_info = config.smtp.contact_info
#        self.connected = False
#        self.message_template = '\r\n'.join(['From: '+self.address,
#                                  'To: {}',
#                                  'Subject: ['+config.name+'] Notifications',
#                                  '',
#                                  'Greetings Human {},',
#                                  '',
#                                  '{}'
#                                  '',
#                                  '',
#                                  'Beep boop,',
#                                  config.name + ' Bot'])
#
#    #TODO deal with smtplib exceptions
#    def connect(self):
#        self.server = smtplib.SMTP(self.hostname)
#        self.server.ehlo()
#        self.server.starttls()
#        self.server.login(self.username, self.passwd)
#        self.connected = True
#
#    #TODO implement saving messages to disk with timestamp if send fails
#    #TODO deal with smtplib exceptions
#    def notify(self, recipient, message):
#        if not self.connected:
#            raise NotifyError('Not connected to SMTP server; cannot send notifications')
#        self.server.sendmail(self.address,
#				self.contact_info[recipient]['address'],
#				self.message_template.format(self.contact_info[recipient]['address'], self.contact_info[recipient]['name'], message)
#                            )
#
#    #TODO deal with smtplib exceptions
#    def close(self):
#        if self.connected:
#            self.server.quit()
#            self.connected = False


