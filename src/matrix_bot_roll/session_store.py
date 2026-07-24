import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


@dataclass
class SavedSession:
    """A previously-established Matrix login, as persisted between runs."""

    user_id: str
    device_id: str
    access_token: str


def load_session(session_file: str, encryption_key: str) -> Optional[SavedSession]:
    """Read and decrypt a previously-saved session, or None if absent/unreadable."""
    if not os.path.isfile(session_file):
        return None

    try:
        with open(session_file, "rb") as f:
            ciphertext = f.read()
        payload = json.loads(Fernet(encryption_key).decrypt(ciphertext))
        return SavedSession(**payload)
    except InvalidToken, ValueError, TypeError, json.JSONDecodeError:
        logger.warning("Saved session at %s is unreadable, discarding", session_file)
        return None


def save_session(session_file: str, encryption_key: str, session: SavedSession) -> None:
    """Encrypt and write `session` to `session_file`, overwriting any previous one."""
    payload = json.dumps(
        {
            "user_id": session.user_id,
            "device_id": session.device_id,
            "access_token": session.access_token,
        }
    ).encode()
    ciphertext = Fernet(encryption_key).encrypt(payload)
    with open(session_file, "wb") as f:
        f.write(ciphertext)
