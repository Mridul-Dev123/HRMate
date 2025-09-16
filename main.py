import imaplib
import smtplib
import email
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

from llm_runner import get_query_response

load_dotenv(override=True)


EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
IMAP_SERVER = os.getenv("IMAP_SERVER")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = 587
POLL_INTERVAL_SECONDS = 2


def extract_body(msg):
    """
    Extract plain text body from email message.
    Falls back to HTML if plain not available.
    """
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            
            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")

        
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return part.get_payload(decode=True).decode(errors="ignore")
    else:
        return msg.get_payload(decode=True).decode(errors="ignore")
    



def check_and_reply_emails():
    """
    Connects to the email server, checks for new emails, and sends a reply.
    This is a synchronous function because 'imaplib' is a blocking library.
    """
    try:
        
        print("Connecting to IMAP server...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")
        print("Polling... looking for new emails.")

        
        status, messages = mail.search(None, "UNSEEN")

        if status == "OK":
            email_ids = messages[0].split()
            if email_ids:
                print(f"Found {len(email_ids)} new email(s).")

                for email_id in email_ids:
                    
                    _, msg_data = mail.fetch(email_id, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    sender = msg["from"]
                    subject = msg["subject"]
                    sender_email = email.utils.parseaddr(sender)[1]
                    embody = extract_body(msg)
                    print(f"  -> Processing email from: {sender_email}")
                    
                    prop=f"Subject: {subject}, body:{embody}"
                    print(f"Msg {prop}")
                    reply_subject = f"Re: {subject}"
                    reply_body = (
                        "Hello,\n\n"
                        "Thank you for your message. This is an automated reply.\n"
                        "I have received your email and will get back to you shortly.\n\n"
                        "Best regards,\n"
                        "The Polling Bot"
                    )
                    res=get_query_response(prop)

                    reply_msg = MIMEMultipart()
                    reply_msg["From"] = EMAIL_USER
                    reply_msg["To"] = sender_email
                    reply_msg["Subject"] = reply_subject
                    reply_msg.attach(MIMEText(res, "plain"))

                    
                    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                        server.starttls()
                        server.login(EMAIL_USER, EMAIL_PASS)
                        server.send_message(reply_msg)
                        print(f"  -> Reply sent successfully to {sender_email}")
        
        mail.logout()

    except Exception as e:
        print(f"An error occurred: {e}")



if __name__ == "__main__":
    print("Starting auto-reply script. Press Ctrl+C to stop.")
    try:
        while True:
            check_and_reply_emails()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nScript stopped by user.")

