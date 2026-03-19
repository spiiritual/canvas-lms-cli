import httpx
from . import auth

HEADERS = {
    "Accept": "application/json+canvas-string-ids",
    "User-Agent": "iCanvas/8.8.1 (30997) iPhone/iOS 26.2.1",
    "Accept-Language": "en-US,en;q=0.9",
}


def make_request(endpoint: str, params: dict = None) -> dict:
    access_token = auth.retrieve_access_token()
    domain = auth.get_domain()

    headers = {
        **HEADERS,
        "Authorization": f"Bearer {access_token}",
    }

    response = httpx.get(
        f"https://{domain}/api/v1/{endpoint}",
        headers=headers,
        params=params,
    )

    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")

    return response.json()
