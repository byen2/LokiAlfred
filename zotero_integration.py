
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ZOTERO_BASE_URL = "http://127.0.0.1:23119/api"


class ZoteroConnectionError(Exception):
    pass


def zotero_get(endpoint):
    """Read data from the local Zotero API. Never modifies Zotero."""
    if not endpoint.startswith("/") or endpoint.startswith("//"):
        raise ValueError("Invalid Zotero API endpoint.")

    url = ZOTERO_BASE_URL + endpoint

    request = Request(
        url,
        headers={
            "Zotero-API-Version": "3",
            "Zotero-Allowed-Request": "1",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        if error.code == 403:
            raise ZoteroConnectionError(
                "Enable local API access in Zotero Settings → Advanced."
            ) from error

        raise ZoteroConnectionError(
            f"Zotero returned HTTP {error.code}."
        ) from error

    except (URLError, TimeoutError) as error:
        raise ZoteroConnectionError(
            "Cannot connect to Zotero. Make sure Zotero Desktop is running."
        ) from error


def get_zotero_status():
    """Check whether the Zotero local API is available."""
    zotero_get("/users/0/collections?limit=1")

    return {
        "connected": True,
        "message": "Connected to Zotero Desktop.",
    }


def get_zotero_collections():
    """List collections in the local user's Zotero library."""
    items = zotero_get("/users/0/collections")

    return [
        {
            "key": item["key"],
            "name": item["data"].get("name", "Untitled Collection"),
            "parent": item["data"].get("parentCollection", False),
            "num_items": item.get("meta", {}).get("numItems", 0),
        }
        for item in items
    ]


def get_zotero_collection_items(collection_key):
    """Read reference metadata from one collection."""
    import re

    if not re.fullmatch(r"[A-Z0-9]{8}", collection_key):
        raise ValueError("Invalid Zotero collection key.")

    items = zotero_get(
        f"/users/0/collections/{collection_key}/items"
    )

    references = []

    for item in items:
        data = item.get("data", {})

        if data.get("itemType") in ("attachment", "note", "annotation"):
            continue

        creators = data.get("creators", [])

        authors = [
            " ".join(
                part for part in [
                    creator.get("firstName", ""),
                    creator.get("lastName", ""),
                ] if part
            ) or creator.get("name", "")
            for creator in creators
        ]

        references.append({
            "key": item.get("key"),
            "title": data.get("title", "Untitled"),
            "authors": authors,
            "date": data.get("date", ""),
            "item_type": data.get("itemType", ""),
            "doi": data.get("DOI", ""),
        })

    return references
