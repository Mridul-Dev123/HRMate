import imaplib
import smtplib
import email
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

from llm_runner import get_query_response, evaluate_email_fitness
from db_utils import init_db, log_interaction

load_dotenv(override=True)


EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = 587
POLL_INTERVAL_SECONDS = 2


def extract_body(msg):
    """
    Extract plain text body from email message.
    Falls back to HTML if plain not available.
    Returns empty string if no body found.
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
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="ignore")
    return ""
    



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
                    try:
                        _, msg_data = mail.fetch(email_id, "(BODY.PEEK[])")
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        sender = msg["from"]
                        subject = msg["subject"] or "(No Subject)"
                        sender_email = email.utils.parseaddr(sender)[1]
                        embody = extract_body(msg)
                        print(f"  -> Processing email from: {sender_email}")
                        
                        prop = f"Subject: {subject}, body:{embody}"
                        print(f"Msg {prop}")
                        
                        if not evaluate_email_fitness(prop):
                            print(f"  -> Email is irrelevant or not an HR query. Skipping reply.")
                            mail.store(email_id, '+FLAGS', '\\Seen')
                            continue
                        
                        print(f"  -> Email is valid. Generating response via Agent...")
                        
                        res = get_query_response(prop, sender_email)

                        if "ESCALATE_TO_HUMAN" in res:
                            print(f"  -> Agent triggered escalation. Forwarding to Human HR...")
                            
                            forward_msg = MIMEMultipart()
                            forward_msg["From"] = EMAIL_USER
                            forward_msg["To"] = "hr-humans@example.com"
                            forward_msg["Subject"] = f"ESCALATION: {subject}"
                            
                            forward_body = f"HRMate could not answer this inquiry from {sender_email}.\n\nOriginal Message:\n{embody}"
                            forward_msg.attach(MIMEText(forward_body, "plain"))
                            
                            try:
                                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                                    server.starttls()
                                    server.login(EMAIL_USER, EMAIL_PASS)
                                    server.send_message(forward_msg)
                                print(f"  -> Forwarded successfully to hr-humans@example.com")
                            except Exception as escalate_e:
                                print(f"  -> Error forwarding escalation: {escalate_e}")
                                
                            # Inform the user
                            res = "Thank you for reaching out. Your inquiry requires human attention. I have escalated this directly to our HR team, and a representative will follow up with you shortly."

                        reply_subject = f"Re: {subject}"

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
                            
                        # explicitly mark as read because we processed and replied
                        mail.store(email_id, '+FLAGS', '\\Seen')
                        print(f"  -> Email marked as read.")
                        
                        # Log interaction to SQLite database
                        log_interaction(sender_email, prop, res)
                        print(f"  -> Saved interaction to Analytics database.")
                    
                    except Exception as email_err:
                        print(f"  -> Error processing email {email_id}: {email_err}")
                        continue
        
        mail.logout()

    except Exception as e:
        print(f"An error occurred: {e}")



if __name__ == "__main__":
    init_db()
    print("Starting auto-reply script. Press Ctrl+C to stop.")
    try:
        while True:
            check_and_reply_emails()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nScript stopped by user.")

