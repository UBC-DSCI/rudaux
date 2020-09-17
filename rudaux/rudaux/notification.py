import smtplib
import subprocess
import time

class NotifyError(Exception):
    def __init__(self, message):
        self.message = message

class Notification(object):
    def __init__(self, config, dry_run):
        self.dry_run = dry_run
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
    def __init__(self, config, dry_run):
        super.__init__(config, dry_run)
        self.address = config.sendmail.address
        self.contact_info = config.sendmail.contact_info
        self.message_template = '\r\n'.join(['From: '+self.address,
                                  'To: {}',
                                  'Subject: ['+config.name+'] Notifications',
                                  '',
                                  'Greetings Human {},',
                                  '',
                                  '{}'
                                  '',
                                  '',
                                  'Beep boop,',
                                  config.name + ' Bot'])

    def notify(self, recipient, message):
        # -i flag: do NOT treat bare dot as EOF
        cmd = ['/usr/sbin/sendmail', f'-f {self.from_addr}', self.contact_info[recipient]['address']]
        msg = self.message_template.format(self.contact_info[recipient]['address'], self.contact_info[recipient]['name'], message)
        proc = subprocess.Popen(cmd, shell=False,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate(input=msg)
        print(f"ret: {proc.returncode}")
        print("stdout:" + str(out))
        print("stderr:" + str(err))

    def connect(self):
        pass

    def close(self):
        pass

class SMTP(Notification):
    def __init__(self, config, dry_run):
        super.__init__(config, dry_run)
        self.hostname = config.smtp.hostname
        self.username = config.smtp.username
        self.passwd = config.smtp.passwd
        self.address = config.smtp.address
        self.contact_info = config.smtp.contact_info
        self.connected = False
        self.message_template = '\r\n'.join(['From: '+self.address,
                                  'To: {}',
                                  'Subject: ['+config.name+'] Notifications',
                                  '',
                                  'Greetings Human {},',
                                  '',
                                  '{}'
                                  '',
                                  '',
                                  'Beep boop,',
                                  config.name + ' Bot'])

    #TODO deal with smtplib exceptions
    def connect(self):
        self.server = smtplib.SMTP(self.hostname)
        self.server.ehlo()
        self.server.starttls()
        self.server.login(self.username, self.passwd)
        self.connected = True

    #TODO implement saving messages to disk with timestamp if send fails
    #TODO deal with smtplib exceptions
    def notify(self, recipient, message):
        if not self.connected:
            raise NotifyError('Not connected to SMTP server; cannot send notifications')
        self.server.sendmail(self.address, 
				self.contact_info[recipient]['address'], 
				self.message_template.format(self.contact_info[recipient]['address'], self.contact_info[recipient]['name'], message)
                            )

    #TODO deal with smtplib exceptions
    def close(self):
        if self.connected:       
            self.server.quit()
            self.connected = False



