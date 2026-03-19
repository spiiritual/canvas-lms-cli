import httpx
import logging
import time
import pickle
from urllib.parse import urlparse, parse_qs

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "iCanvas/8.8.1 (30997) iPhone/iOS 26.2.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def get_domain() -> str:
    try:
        with open("canvas_tokens.pkl", "rb") as f:
            data = pickle.load(f)
    except FileNotFoundError:
        raise Exception("No tokens found. Please authenticate first.")

    return data["domain"]


def retrieve_access_token() -> str:
    try:
        with open("canvas_tokens.pkl", "rb") as f:
            data = pickle.load(f)
    except FileNotFoundError:
        raise Exception(
            "No tokens found. Please authenticate first with canvas-lms-cli authenticate <link>."
        )

    expiry = data["access_token_expiry"]

    if time.time() > expiry:
        logging.info("Access token expired, refreshing...")

        refresh_token = data["refresh_token"]
        client_id = data["client_id"]
        client_secret = data["client_secret"]
        domain = data["domain"]

        access_token = refresh_access_token(
            client_id, client_secret, domain, refresh_token
        )
        save_tokens_to_file(
            access_token, client_id, client_secret, domain, refresh_token
        )
        return access_token
    else:
        return data["access_token"]


def refresh_access_token(
    client_id: str,
    client_secret: str,
    domain: str,
    refresh_token: str,
) -> str:
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

    if r.status_code != 200:
        raise Exception(f"Error refreshing token: {r.status_code} - {r.text}")

    data = r.json()
    access_token = data["access_token"]

    return access_token


def save_tokens_to_file(
    access_token: str,
    client_id: str,
    client_secret: str,
    domain: str,
    refresh_token: str,
) -> None:
    data = {
        "access_token": access_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "domain": domain,
        "refresh_token": refresh_token,
        "access_token_expiry": time.time()
        + 3600,  # Canvas access tokens expire after 1 hour
    }

    with open("canvas_tokens.pkl", "wb") as f:
        pickle.dump(data, f)


def authenticate_from_url(url: str) -> None:
    code, domain = parse_qr_code_url(url)
    client_id, client_secret = get_client_info(domain)
    access_token, refresh_token = exchange_code_for_tokens(
        domain, client_id, client_secret, code
    )
    save_tokens_to_file(
        access_token=access_token,
        client_id=client_id,
        client_secret=client_secret,
        domain=domain,
        refresh_token=refresh_token,
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
) -> tuple[str, str]:
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

    return (access_token, refresh_token)
