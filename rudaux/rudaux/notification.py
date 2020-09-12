import smtplib

class SMTPOpenError(Exception):
    def __init__(self):
        pass

class SMTPSendError(Exception):
    def __init__(self):
        pass

class SMTP(object):
    def __init__(self, config, dry_run):
        self.dry_run = dry_run
        self.server = smtplib.SMTP(config.smtp.hostname)
        self.server.ehlo()
        self.server.starttls()
        self.server.login(config.smtp.username, config.smtp.passwd)
        self.from_address = config.smtp.address
        self.message_template = '\r\n'.join(['From: '+config.smtp.address,
                                  'To: {}',
                                  'Subject: {}',
                                  '',
                                  'Greetings {},',
                                  '',
                                  '{}'
                                  '',
                                  'Beep boop,',
                                  config.name + ' Email Bot'])

    def notify(self, recipient_name, recipient_address, subject, message):
        self.server.sendmail(self.from_address, 
				recipient_address, 
				self.message_template.format(recipient_address, subject, recipient_name, message)
                            )


    def close(self):
        self.server.quit()
