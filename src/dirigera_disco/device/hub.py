import os

import dirigera
from dotenv import load_dotenv


def connect() -> dirigera.Hub:
    """Open a hub connection from DIRIGERA_IP and DIRIGERA_TOKEN."""
    load_dotenv()
    ip_address = os.environ.get("DIRIGERA_IP", "")
    token = os.environ.get("DIRIGERA_TOKEN", "")
    missing = [
        name
        for name, value in (("DIRIGERA_IP", ip_address), ("DIRIGERA_TOKEN", token))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing {', '.join(missing)}. Set them in the environment or in .env."
        )
    return dirigera.Hub(token=token, ip_address=ip_address)
