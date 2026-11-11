import logging
import requests
from django.conf import settings

logger = logging.getLogger("amour.email")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_brevo_email(to_email: str, to_name: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """
    Sends a transactional email via Brevo REST API v3.
    """
    api_key = getattr(settings, "BREVO_API_KEY", "")
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "ankesh3905222@gmail.com")
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "Amour AI")

    if not api_key:
        logger.error("BREVO_API_KEY is not configured in settings. Cannot send email.")
        return False

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    if text_content:
        payload["textContent"] = text_content

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=12)
        if response.status_code in (200, 201, 202):
            logger.info("Brevo email dispatched successfully (status %s)", response.status_code)
            return True
        else:
            logger.error("Brevo email dispatch failed with HTTP %s", response.status_code)
            return False
    except Exception as exc:
        logger.error("Brevo email network error: %s", type(exc).__name__)
        return False


def send_verification_email(to_email: str, name: str, verification_link: str, code: str) -> bool:
    """
    Sends email confirmation link + 6-digit confirmation code for new signup.
    """
    subject = "Confirm Your Amour AI Account"
    display_name = name.strip() if name else "there"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confirm Your Amour AI Account</title>
</head>
<body style="margin: 0; padding: 0; background-color: #09090B; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #FFFFFF;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #09090B; padding: 40px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card -->
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 520px; background-color: #121216; border: 1px solid #27272A; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
          <!-- Header Bar with Brand Accent -->
          <tr>
            <td style="background: linear-gradient(90deg, #F43F5E 0%, #FB7185 100%); height: 4px;"></td>
          </tr>
          <tr>
            <td style="padding: 36px 32px 24px 32px; text-align: center;">
              <!-- Logo / Wordmark -->
              <div style="display: inline-block; padding: 10px 18px; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 12px; margin-bottom: 20px;">
                <span style="font-size: 20px; font-weight: 800; letter-spacing: 3px; color: #F43F5E;">AMOUR AI</span>
              </div>
              <h1 style="margin: 0 0 10px 0; font-size: 24px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.5px;">Confirm Your Email</h1>
              <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #A1A1AA;">
                Welcome, {display_name}! You're one step away from joining your private AI companions.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 32px 28px 32px;">
              <!-- Action Button -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 8px 0 24px 0;">
                <tr>
                  <td align="center">
                    <a href="{verification_link}" target="_blank" style="display: inline-block; width: 100%; box-sizing: border-box; text-align: center; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 24px; border-radius: 10px; letter-spacing: 0.2px; box-shadow: 0 4px 14px rgba(244, 63, 94, 0.35);">
                      Confirm My Account
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Divider -->
              <div style="text-align: center; margin: 24px 0; position: relative;">
                <div style="border-top: 1px solid #27272A; margin-top: 10px;"></div>
                <span style="display: inline-block; background-color: #121216; padding: 0 12px; color: #71717A; font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; position: relative; top: -10px;">Or Enter In App</span>
              </div>

              <!-- 6-Digit Code Box -->
              <div style="background-color: #18181B; border: 1px dashed rgba(244, 63, 94, 0.4); border-radius: 12px; padding: 18px 20px; text-align: center; margin-bottom: 24px;">
                <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #A1A1AA; margin-bottom: 6px;">Confirmation Code</div>
                <div style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #FFFFFF; font-family: monospace;">{code}</div>
              </div>

              <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #71717A; text-align: center;">
                This link and code will expire in 24 hours.<br>
                If you didn't create an account with Amour AI, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0E0E12; border-top: 1px solid #1F1F23; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #52525B;">
                &copy; 2026 Amour AI. Private, intelligent companions.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    text_content = f"""
Welcome to Amour AI, {display_name}!

Please confirm your email address by tapping the link below:
{verification_link}

Or enter this 6-digit confirmation code in the app:
{code}

This link and code expire in 24 hours. If you did not create an account, please ignore this email.

— The Amour AI Team
"""
    return send_brevo_email(to_email, name, subject, html_content, text_content)


def send_password_reset_email(to_email: str, name: str, reset_link: str, code: str) -> bool:
    """
    Sends password reset link + 6-digit reset code via Brevo.
    """
    subject = "Reset Your Amour AI Password"
    display_name = name.strip() if name else "there"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your Amour AI Password</title>
</head>
<body style="margin: 0; padding: 0; background-color: #09090B; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #FFFFFF;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #09090B; padding: 40px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card -->
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 520px; background-color: #121216; border: 1px solid #27272A; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
          <!-- Header Bar with Brand Accent -->
          <tr>
            <td style="background: linear-gradient(90deg, #F43F5E 0%, #FB7185 100%); height: 4px;"></td>
          </tr>
          <tr>
            <td style="padding: 36px 32px 24px 32px; text-align: center;">
              <!-- Logo / Wordmark -->
              <div style="display: inline-block; padding: 10px 18px; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 12px; margin-bottom: 20px;">
                <span style="font-size: 20px; font-weight: 800; letter-spacing: 3px; color: #F43F5E;">AMOUR AI</span>
              </div>
              <h1 style="margin: 0 0 10px 0; font-size: 24px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.5px;">Password Reset Request</h1>
              <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #A1A1AA;">
                Hi {display_name}, we received a request to reset your Amour AI password.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 32px 28px 32px;">
              <!-- Action Button -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 8px 0 24px 0;">
                <tr>
                  <td align="center">
                    <a href="{reset_link}" target="_blank" style="display: inline-block; width: 100%; box-sizing: border-box; text-align: center; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 24px; border-radius: 10px; letter-spacing: 0.2px; box-shadow: 0 4px 14px rgba(244, 63, 94, 0.35);">
                      Reset My Password
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Divider -->
              <div style="text-align: center; margin: 24px 0; position: relative;">
                <div style="border-top: 1px solid #27272A; margin-top: 10px;"></div>
                <span style="display: inline-block; background-color: #121216; padding: 0 12px; color: #71717A; font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; position: relative; top: -10px;">Or Enter In App</span>
              </div>

              <!-- 6-Digit Code Box -->
              <div style="background-color: #18181B; border: 1px dashed rgba(244, 63, 94, 0.4); border-radius: 12px; padding: 18px 20px; text-align: center; margin-bottom: 24px;">
                <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #A1A1AA; margin-bottom: 6px;">Reset Verification Code</div>
                <div style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #FFFFFF; font-family: monospace;">{code}</div>
              </div>

              <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #71717A; text-align: center;">
                For security, this link and code expire in 1 hour.<br>
                If you did not request a password reset, no action is needed — your account remains secure.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0E0E12; border-top: 1px solid #1F1F23; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #52525B;">
                &copy; 2026 Amour AI. Private, intelligent companions.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    text_content = f"""
Hi {display_name},

A password reset was requested for your Amour AI account.

Reset your password using the link below:
{reset_link}

Or enter this 6-digit code in the app:
{code}

This link and code expire in 1 hour. If you did not request this, please disregard this email.

— The Amour AI Team
"""
    return send_brevo_email(to_email, name, subject, html_content, text_content)
