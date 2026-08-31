

def send_notification_email(user_email, subject, body, credentials):

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import base64

    # Modern Google Auth credentials object
    creds = Credentials(token=credentials)

    service = build('gmail', 'v1', credentials=creds)

    message = {
        'raw': base64.urlsafe_b64encode(
            f'From: {user_email}\n'
            f'To: {user_email}\n'
            f'Subject: {subject}\n\n'
            f'{body}'.encode('utf-8')
        ).decode('utf-8')
    }

    service.users().messages().send(userId='me', body=message).execute()
