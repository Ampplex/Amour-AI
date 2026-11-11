import re
import logging
from typing import Any

# Pre-compiled high-performance regular expressions for PII & sensitive credential detection

# 1. Email Addresses
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# 2. Credit / Debit Cards (13-19 digits, with or without spaces/hyphens)
CARD_REGEX = re.compile(
    r'\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b'
)

# 3. Phone Numbers (US, International + Indian mobile numbers)
PHONE_REGEX = re.compile(
    r'(?:\+?(\d{1,3})[-.\s]?)?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b|'
    r'(?:\+91[\-\s]?)?[6-9]\d{9}\b'
)

# 4. Social Security Numbers (US SSN: XXX-XX-XXXX)
SSN_REGEX = re.compile(
    r'\b\d{3}-\d{2}-\d{4}\b'
)

# 5. Indian Aadhaar Numbers (XXXX XXXX XXXX)
AADHAAR_REGEX = re.compile(
    r'\b\d{4}\s\d{4}\s\d{4}\b'
)

# 6. IPv4 Addresses (ignoring loopback / unassigned)
IPV4_REGEX = re.compile(
    r'\b(?!127\.0\.0\.1|0\.0\.0\.0)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
)

# 7. JWT Tokens (header.payload.signature)
JWT_REGEX = re.compile(
    r'\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+\b'
)

# 8. Known API Keys & Bearer Tokens (OpenAI, Brevo, Neon, Groq, Bearer headers)
API_KEY_REGEX = re.compile(
    r'\b(?:sk-[a-zA-Z0-9_-]{20,}|xkeysib-[a-zA-Z0-9]{30,}|npg_[a-zA-Z0-9]{10,}|gsk_[a-zA-Z0-9]{20,})\b|'
    r'\b[Bb]earer\s+[A-Za-z0-9\-._~+/]+=*'
)

# 9. Key-Value Passwords & Secret Parameters (JSON, query string, or config lines)
SENSITIVE_KV_REGEX = re.compile(
    r'(["\']?(?:password|passwd|secret|api_key|access_token|user_key|client_key)["\']?\s*[:=]\s*["\']?)([^"\'\s&,}{]+)(["\']?)',
    re.IGNORECASE
)


def redact_pii(text: str) -> str:
    """
    Sanitizes a string by redacting personally identifiable information (PII)
    and sensitive credentials (emails, phones, credit cards, SSNs, IPs, tokens, passwords).
    """
    if not text or not isinstance(text, str):
        return text

    # Redact sensitive key-value pairs (passwords, secret tokens)
    text = SENSITIVE_KV_REGEX.sub(r'\1[REDACTED_SECRET]\3', text)

    # Redact known API keys & Bearer tokens
    text = API_KEY_REGEX.sub('[REDACTED_TOKEN]', text)

    # Redact JWT tokens
    text = JWT_REGEX.sub('[REDACTED_JWT]', text)

    # Redact credit / debit card numbers
    text = CARD_REGEX.sub('[REDACTED_CARD]', text)

    # Redact government IDs
    text = SSN_REGEX.sub('[REDACTED_SSN]', text)
    text = AADHAAR_REGEX.sub('[REDACTED_AADHAAR]', text)

    # Redact email addresses
    text = EMAIL_REGEX.sub('[REDACTED_EMAIL]', text)

    # Redact phone numbers
    text = PHONE_REGEX.sub('[REDACTED_PHONE]', text)

    # Redact public IP addresses
    text = IPV4_REGEX.sub('[REDACTED_IP]', text)

    return text


def mask_email(email: str) -> str:
    """
    Masks an email for user-facing confirmation (e.g., j***e@domain.com).
    """
    if not email or "@" not in email:
        return "[REDACTED_EMAIL]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """
    Masks a phone number (e.g., +91 ******4321).
    """
    if not phone or len(phone) < 4:
        return "[REDACTED_PHONE]"
    return f"{'*' * (len(phone) - 4)}{phone[-4:]}"


class PIIRedactionFilter(logging.Filter):
    """
    Global Django/Python Logging Filter.
    Intercepts all log records emitted to console or log streams and redacts
    PII, secrets, and auth tokens automatically.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_pii(record.msg)

            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: redact_pii(str(v)) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact_pii(str(arg)) if isinstance(arg, str) else arg
                        for arg in record.args
                    )
        except Exception:
            # Logging filter must never crash the application
            pass

        return True
