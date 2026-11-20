import httpx
import json
import logging
import os
import pickle
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "iCanvas/8.8.1 (30997) iPhone/iOS 26.2.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

# Fixed location so the CLI works from any directory (e.g. when an agent runs it).
CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "canvas-lms-cli"
)
TOKEN_FILE = CONFIG_DIR / "tokens.json"
LEGACY_TOKEN_FILE = Path("canvas_tokens.pkl")

# Fallback if Canvas doesn't send expires_in (its access tokens normally last 1 hour).
DEFAULT_EXPIRES_IN = 3600
EXPIRY_MARGIN = 60


def load_tokens() -> dict:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())

    # One-time migration from the old pickle file in the current directory.
    if LEGACY_TOKEN_FILE.exists():
        with open(LEGACY_TOKEN_FILE, "rb") as f:
            data = pickle.load(f)
        write_tokens(data)
        logging.info(f"Migrated tokens from {LEGACY_TOKEN_FILE} to {TOKEN_FILE}")
        return data

    raise Exception(
        "No tokens found. Please authenticate first with canvas-lms-cli authenticate <link>."
    )


def write_tokens(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Create with owner-only permissions: this file grants access to your account.
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)


def get_domain() -> str:
    return load_tokens()["domain"]


def retrieve_access_token() -> str:
    data = load_tokens()

    if time.time() > data["access_token_expiry"]:
        logging.info("Access token expired, refreshing...")
        access_token, refresh_token, expires_in = refresh_access_token(
            data["client_id"], data["client_secret"], data["domain"], data["refresh_token"]
        )
        save_tokens_to_file(
            access_token,
            data["client_id"],
            data["client_secret"],
            data["domain"],
            refresh_token,
            expires_in,
        )
        return access_token

    return data["access_token"]


def refresh_access_token(
    client_id: str,
    client_secret: str,
    domain: str,
    refresh_token: str,
) -> tuple[str, str, int]:
    r = httpx.post(
        f"https://{domain}/login/oauth2/token",
        headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Accept": "application/json+canvas-string-ids",
        },
        json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )

    # 400/401 here means Canvas no longer accepts the refresh token (revoked in
    # Approved Integrations, logged out of mobile sessions, or disabled by the school).
    if r.status_code in (400, 401):
        raise Exception(
            "Your Canvas login has expired or was revoked. Generate a new Mobile Login "
            "QR code and run: canvas-lms-cli authenticate <LINK>\n"
            f"(Canvas said: {r.status_code} - {r.text})"
        )
    if r.status_code != 200:
        raise Exception(f"Error refreshing token: {r.status_code} - {r.text}")

    data = r.json()
    # Canvas normally keeps the same refresh token, but use a new one if it sends one.
    return (
        data["access_token"],
        data.get("refresh_token", refresh_token),
        data.get("expires_in", DEFAULT_EXPIRES_IN),
    )


def save_tokens_to_file(
    access_token: str,
    client_id: str,
    client_secret: str,
    domain: str,
    refresh_token: str,
    expires_in: int = None,
) -> None:
    if expires_in is None:
        expires_in = DEFAULT_EXPIRES_IN

    data = {
        "access_token": access_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "domain": domain,
        "refresh_token": refresh_token,
        # Refresh a minute early so a token never expires mid-request.
        "access_token_expiry": time.time() + expires_in - EXPIRY_MARGIN,
    }

    write_tokens(data)


def authenticate_from_url(url: str) -> None:
    code, domain = parse_qr_code_url(url)
    client_id, client_secret = get_client_info(domain)
    access_token, refresh_token, expires_in = exchange_code_for_tokens(
        domain, client_id, client_secret, code
    )
    save_tokens_to_file(
        access_token=access_token,
        client_id=client_id,
        client_secret=client_secret,
        domain=domain,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )

    print("Authentication successful!")


def parse_qr_code_url(url: str) -> tuple[str, str]:
    params = parse_qs(urlparse(url).query)
    code = params["code"][0]
    domain = params["domain"][0]

    return (code, domain)


def get_client_info(domain: str) -> tuple[str, str, str]:
    r = httpx.get(
        "https://sso.canvaslms.com/api/v1/mobile_verify.json",
        headers=HEADERS,
        params={"domain": domain},
    )

    if r.status_code != 200:
        raise Exception(f"Error: {r.status_code} - {r.text}")

    data = r.json()
    client_id = data["client_id"]
    client_secret = data["client_secret"]

    return (client_id, client_secret)


def exchange_code_for_tokens(
    domain: str, client_id: str, client_secret: str, code: str
) -> tuple[str, str, int]:
    r = httpx.post(
        f"https://{domain}/login/oauth2/token",
        headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Accept": "application/json+canvas-string-ids",
        },
        json={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
    )

    if r.status_code != 200:
        print(domain)
        raise Exception(f"Error: {r.status_code} - {r.text}")

    data = r.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]
    expires_in = data.get("expires_in", DEFAULT_EXPIRES_IN)

    return (access_token, refresh_token, expires_in)
