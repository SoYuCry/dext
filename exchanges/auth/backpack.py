"""
API authentication and signature module
"""
import base64
import nacl.signing
import sys
from typing import Optional
from exchanges.logger import setup_logger

logger = setup_logger("exchanges.auth")

def create_signature(secret_key: str, message: str) -> Optional[str]:
    """
    Create an API signature

    Args:
        secret_key: API secret key
        message: The message to sign

    Returns:
        Signature string, or None if signing fails
    """
    try:
        # Attempt to decode the key and create the signature
        decoded_key = base64.b64decode(secret_key)
        signing_key = nacl.signing.SigningKey(decoded_key)
        signature = signing_key.sign(message.encode('utf-8')).signature
        return base64.b64encode(signature).decode('utf-8')
    except Exception as e:
        logger.error(f"Signature creation failed: {e}")
        logger.error("Unable to create API signature, program will terminate")
        # Force terminate the program
        sys.exit(1)
