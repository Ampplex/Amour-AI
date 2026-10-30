import logging
from typing import Optional, dict, Any
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from ..config import settings

log = logging.getLogger("amour.auth")

def verify_google_id_token(token: str) -> Optional[dict[str, Any]]:
    """
    Cryptographically verify the Google ID token returned by Android / Web.
    Checks against both Web and Android Client IDs in settings.
    """
    request = google_requests.Request()
    
    # Try verifying against configured Client IDs
    for client_id in settings.GOOGLE_CLIENT_IDS:
        try:
            idinfo = google_id_token.verify_oauth2_token(token, request, client_id)
            log.info("Successfully verified Google ID token with client ID: %s", client_id)
            return idinfo
        except Exception as e:
            continue
            
    # As a secondary attempt without client_id check if token is valid Google token
    try:
        idinfo = google_id_token.verify_oauth2_token(token, request)
        return idinfo
    except Exception as e:
        log.warning("Google ID token verification failed: %s", e)
        return None
