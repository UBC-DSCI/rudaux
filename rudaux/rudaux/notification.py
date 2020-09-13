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
        self.contact_info = config.smtp.contact_info

    def notify(self, recipient, subject, message):
        self.server.sendmail(self.from_address, 
				self.contact_info[recipient]['address'], 
				self.message_template.format(self.contact_info[recipient]['address'], subject, self.contact_info[recipient]['name'], message)
                            )


    def close(self):
        self.server.quit()
