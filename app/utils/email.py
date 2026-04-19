import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_otp_email(to_email: str, otp_code: str):
    msg = MIMEMultipart()
    msg['From'] = settings.SMTP_EMAIL
    msg['To'] = to_email
    msg['Subject'] = "Docmosiss: Your Verification Code"
    
    body = f"""
    Welcome to Docmosiss!
    
    Your 6-digit verification code is: {otp_code}
    
    This code will expire in 15 minutes. If you didn't request this, you can safely ignore this email.
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to Gmail's secure SMTP server
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"OTP sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        # In production, you might want to log this properly