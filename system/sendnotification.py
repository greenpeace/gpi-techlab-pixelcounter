

def send_notification_email(user_email, subject, body, credentials):
    from oauth2client.client import AccessTokenCredentials
    from googleapiclient.discovery import build
    import base64

    # Create an AccessTokenCredentials object using the stored credentials.
    access_token_credentials = AccessTokenCredentials(credentials, 'user-agent-value')

    # Create a Gmail service instance using the credentials.
    service = build('gmail', 'v1', credentials=access_token_credentials)

    # Create the email message.
    message = {
        'raw': base64.urlsafe_b64encode(
            f'From: {user_email}\nTo: {user_email}\nSubject: {subject}\n\n{body}'
            .encode('utf-8')
        ).decode('utf-8')
    }

    # Send the email.
    service.users().messages().send(userId='me', body=message).execute()
