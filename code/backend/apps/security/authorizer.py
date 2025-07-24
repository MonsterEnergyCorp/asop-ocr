import base64
from core.config import config

def is_basic_auth_token(token: str) -> bool:
    return token.startswith("Basic ") if token else False

def validate_basic_auth_token(token: str) -> bool:
    """
    Validate the Basic Auth Token
    """
    
    token = token[len("Basic "):]
    try:
        decoded_token = base64.b64decode(token).decode("utf-8")
    except (base64.binascii.Error, UnicodeDecodeError):
        return False

    return decoded_token == f"{config.api_auth_username}:{config.api_auth_password}"

def validate_token(token: str) -> bool:
    """
    Validate the token
    """
    if is_basic_auth_token(token):
        return validate_basic_auth_token(token)
    # In future, we can add more token types here
    return False