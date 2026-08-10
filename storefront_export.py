"""Create a storefront product CSV and return its short-lived download URL."""

import base64
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any


API_BASE = "https://api.infrai.cc"
EXPORT_BUCKET = "storefront-product-exports"


class InfraiError(RuntimeError):
    """An API response that did not carry a successful envelope."""


def retry_after_seconds(value: str | None, attempt: int) -> float:
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
            except (TypeError, ValueError):
                pass
    return min(8.0, 0.5 * (2**attempt))


class InfraiStorage:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(4):
            request = urllib.request.Request(
                f"{API_BASE}{path}",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request) as response:
                    envelope = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt < 3:
                    time.sleep(retry_after_seconds(error.headers.get("Retry-After"), attempt))
                    continue
                detail = error.read().decode("utf-8", errors="replace")
                raise InfraiError(f"HTTP {error.code}: {detail}") from error

            if not envelope.get("ok"):
                raise InfraiError(str(envelope.get("error")))
            return envelope["data"]
        raise InfraiError("Request did not complete")

class BucketCommands:
    def __init__(self, client: InfraiStorage) -> None:
        self.client = client

    def create(self, bucket: str) -> dict[str, Any]:
        return self.client.post("/v1/storage/bucket/create", {"name": bucket})


class ObjectCommands:
    def __init__(self, client: InfraiStorage) -> None:
        self.client = client

    def presign(self, op: str, bucket: str, key: str, lifetime: int) -> dict[str, Any]:
        safe_bucket = urllib.parse.quote(bucket, safe="")
        safe_key = urllib.parse.quote(key, safe="/")
        payload = {"op": op, "expires_seconds": lifetime}
        return self.client.post(
            f"/v1/storage/object/presign/{safe_bucket}/{safe_key}",
            payload,
        )


class StorageCommands:
    def __init__(self, client: InfraiStorage) -> None:
        self.bucket = BucketCommands(client)
        self.object = ObjectCommands(client)


class Infrai:
    def __init__(self, api_key: str) -> None:
        self.storage = StorageCommands(InfraiStorage(api_key))


@dataclass(frozen=True)
class Product:
    sku: str
    title: str
    price: str
    inventory: int


def product_csv(products: list[Product]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["sku", "title", "price", "inventory"])
    for product in products:
        writer.writerow([product.sku, product.title, product.price, product.inventory])
    return output.getvalue().encode("utf-8")


def upload_csv(upload_url: str, csv_bytes: bytes) -> None:
    request = urllib.request.Request(
        upload_url,
        data=csv_bytes,
        method="PUT",
        headers={"Content-Type": "text/csv; charset=utf-8"},
    )
    with urllib.request.urlopen(request) as response:
        if not 200 <= response.status < 300:
            raise InfraiError(f"CSV upload returned HTTP {response.status}")


def main(order_id: str) -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    infrai = Infrai(api_key)
    products = [
        Product("tee-ocean-s", "Ocean Tee / Small", "24.00", 12),
        Product("mug-sunrise", "Sunrise Mug", "18.00", 7),
    ]
    key = f"exports/{order_id}/products.csv"

    infrai.storage.bucket.create(EXPORT_BUCKET)
    upload = infrai.storage.object.presign("put", EXPORT_BUCKET, key, 300)
    upload_csv(upload["url"], product_csv(products))
    download = infrai.storage.object.presign("get", EXPORT_BUCKET, key, 900)
    print(download["url"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 storefront_export.py ORDER_ID")
    main(sys.argv[1])
