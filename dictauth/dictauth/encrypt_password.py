import secrets
import hashlib
import re
import getpass

def encrypt_password():
    #create salt and pw validator regex
    validator_regex = re.compile(r"^(?=.*[A-Za-z])(?=.*[0-9]).{8,}$")
    salt = secrets.token_hex(64)
    
    print('---------------------------------------------------------------------')
    print('---------------------------------------------------------------------')
    print('This script converts a plain text password into a secure hash digest.')
    print('Please input your password of choice.')
    print('Your password must be a minimum of 8 chars, and must contain at least')
    print('one letter and one number.')
    print('---------------------------------------------------------------------')
    print('---------------------------------------------------------------------')
    pw = None
    while True:
        #get a password
        pw = getpass.getpass('Input your password: ')
        #validate
        while not validator_regex.search(pw):
            print('Password must be a minimum of 8 chars, and must contain at least one letter and one number')
            pw = getpass.getpass('Input your password: ')
    
        #encode as bytes
        try:
            salted_pw_bytes = (pw+salt).encode('utf-8')
        except Exception as e:
            print('Password cannot be utf-8 encoded. Try again.')
            print('Error message: ' + str(e))
            continue
    
        #repeat it to verify
        pw2 = getpass.getpass('Repeat your password: ')
        if pw != pw2:
            print('Passwords did not match. Try again.') 
        else:
            break
    
    digest = hashlib.sha512(salted_pw_bytes).hexdigest()
    
    print('')
    print('Successfully hashed password.')
    print('')
    
    print('-------------------------------------------------------')
    print('----Send these two values to your course instructor----')
    print('-------------------------------------------------------')
    print('Salt:        ' + salt)
    print('SHA512 Hash: ' + digest)
    print('-------------------------------------------------------')




