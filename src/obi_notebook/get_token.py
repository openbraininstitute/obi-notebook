"""A wrapper for get_token from obi_auth that tries to use an environment variable first."""

from os import getenv
from time import time

from jwt.exceptions import DecodeError
from obi_auth import get_token as auth_get_token
from obi_auth import get_token_info

MIN_TIME_LEFT_SEC = 600


def get_token(auth_mode="daf"):
    """Gets an access token for the user."""
    token = getenv("OBI_ACCESS_TOKEN")
    if token is None:
        return auth_get_token(auth_mode=auth_mode)

    try:
        token_info = get_token_info(token)
    except DecodeError:
        return auth_get_token(auth_mode=auth_mode)

    if (token_info["exp"] - time()) <= MIN_TIME_LEFT_SEC:
        return auth_get_token(auth_mode=auth_mode)
    return token
