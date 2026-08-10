import unittest
from unittest.mock import Mock

from storefront_export import (
    BucketCommands,
    ObjectCommands,
    Product,
    product_csv,
    retry_after_seconds,
)


class StorefrontExportTests(unittest.TestCase):
    def test_csv_has_a_product_row_for_the_catalog_download(self) -> None:
        payload = product_csv([Product("tee-ocean-s", "Ocean Tee / Small", "24.00", 12)])
        self.assertEqual(
            payload.decode("utf-8"),
            "sku,title,price,inventory\r\ntee-ocean-s,Ocean Tee / Small,24.00,12\r\n",
        )

    def test_retry_after_prefers_a_server_delay(self) -> None:
        self.assertEqual(retry_after_seconds("2", 0), 2.0)

    def test_bucket_create_sends_required_name(self) -> None:
        client = Mock()
        BucketCommands(client).create("exports-test")
        client.post.assert_called_once_with(
            "/v1/storage/bucket/create", {"name": "exports-test"}
        )

    def test_presign_sends_expires_seconds(self) -> None:
        client = Mock()
        ObjectCommands(client).presign("put", "exports-test", "catalog.csv", 300)
        client.post.assert_called_once_with(
            "/v1/storage/object/presign/exports-test/catalog.csv",
            {"op": "put", "expires_seconds": 300},
        )


if __name__ == "__main__":
    unittest.main()
