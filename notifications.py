import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

def send_alert_email(receiver_email, subject, product_name, product_url, old_price, new_price, image_url):
    sender_email = Config.SMTP_SENDER
    app_password = Config.SMTP_APP_PASSWORD

    if not sender_email or not app_password:
        logger.warning("Email credentials not configured. Skipping email notification.")
        return False

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 10px;">
          <h2 style="color: #4F46E5; text-align: center;">Price Drop Alert! 🎉</h2>
          <p>Hi there,</p>
          <p>Great news! The price of <strong>{product_name}</strong> has dropped.</p>
          <div style="text-align: center; margin: 20px 0;">
            <img src="{image_url}" alt="Product Image" style="max-width: 200px; border-radius: 8px;">
          </div>
          <table style="width: 100%; text-align: center; margin-bottom: 20px;">
            <tr>
              <td style="color: #777;">Previous Price</td>
              <td style="color: #4CAF50; font-weight: bold; font-size: 1.2em;">New Price</td>
            </tr>
            <tr>
              <td style="text-decoration: line-through; color: #777;">₹{old_price}</td>
              <td style="color: #4CAF50; font-size: 1.5em; font-weight: bold;">₹{new_price}</td>
            </tr>
          </table>
          <div style="text-align: center;">
            <a href="{product_url}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">View Deal Now</a>
          </div>
          <p style="margin-top: 30px; font-size: 0.9em; color: #888; text-align: center;">
            You can pause or delete this alert from your SAYU dashboard.
          </p>
        </div>
      </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent successfully to {receiver_email}")
        return True
    except Exception as e:
        logger.error(f"Email sending failed to {receiver_email}: {e}")
        return False

def fire_webhook(product_name, product_url, new_price):
    webhook_url = Config.WEBHOOK_URL
    if not webhook_url:
        return
    
    payload = {
        "text": f"🎯 **Price Drop Alert**: {product_name} is now down to ₹{new_price}!\n[View Deal]({product_url})"
    }
    try:
        requests.post(webhook_url, json=payload, timeout=5)
        logger.info("Webhook fired successfully.")
    except Exception as e:
        logger.error(f"Webhook execution failed: {e}")

def notify_price_drop(user_email, product_name, product_url, old_price, new_price, image_url):
    subject = f"Price Drop Alert: {product_name[:30]}..."
    send_alert_email(user_email, subject, product_name, product_url, old_price, new_price, image_url)
    fire_webhook(product_name, product_url, new_price)
