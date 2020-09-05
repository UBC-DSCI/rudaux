import smtplib

class SMTPOpenError(Exception):
    def __init__(self):
        pass

class SMTPSendError(Exception):
    def __init__(self):
        pass

class SMTP(object):
    def __init__(self, course):
        self.server = smtplib.SMTP(course.config.smtp.hostname)
        self.server.ehlo()
        self.server.starttls()
        self.server.login(course.config.smtp.username, course.config.smtp.passwd)
        self.from_address = course.config.smtp.address
        self.message_template = '\r\n'.join(['From: '+course.config.smtp.address,
                                  'To: {}',
                                  'Subject: {}',
                                  '',
                                  'Greetings {},',
                                  '',
                                  '{}'
                                  '',
                                  'Beep boop,',
                                  course.config.name + ' Email Bot'])

    def notify(self, recipient_name, recipient_address, subject, message):
        self.server.sendmail(self.from_address, 
				recipient_address, 
				self.message_template.format(recipient_address, subject, recipient_name, message)
                            )


    def close(self):
        self.server.quit()
