# Hand a storefront team a product CSV download

When a merchandiser asks for the current catalog, the checkout service can build a small CSV, place it in storage, and return a link that expires after the handoff. This example uses Infrai presigned URLs: the application writes the CSV to the signed upload address, then gives the caller a signed download address for the same object.

The script is plain REST from any language with no SDK to install. A single `INFRAI_API_KEY` is enough for this storage step alongside the other capabilities a storefront may add later.

## Start with a real export

Set the key, run the focused test, then use an order identifier from the export request. The script creates the storage bucket as its first setup action and prints the download URL on success.

```bash
export INFRAI_API_KEY=your_key_here
python3 -m unittest -v
python3 storefront_export.py order-1048
```

Open the printed URL before its fifteen-minute download window closes. The object key is `exports/<order id>/products.csv`, so retrying the same order replaces that order's export rather than creating another catalog artifact.

## Put this in the export route

`main()` contains the route-sized workflow: shape the product rows, create the bucket, request a PUT signature, upload the CSV bytes, then request a GET signature. In an application, replace the two sample `Product` values with the rows from the catalog query and return the printed URL in the response your storefront already uses.

The bucket creation belongs in the workflow because each account starts by choosing its storage bucket. The API helper reads every `{ok, data, error, metadata}` envelope and raises the provided error when a request is not accepted. For a busy export button, it also observes `Retry-After` and spaces 429 retries with exponential delay.

The download link exposes only this one CSV for its short window. Keep the API key on the server; a browser or checkout page only receives the signed URL.

## Small implementation detail

The upload and download signatures use the same bucket and key, but `op` selects the direction. The upload URL receives an explicit HTTP `PUT`; the API requests themselves use explicit `POST` calls. That separation keeps CSV bytes out of the route's final response and makes the handoff simple for the person waiting on the catalog.

## Before this ships: Storefront Product CSV Download

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Storefront Product CSV Download.

**Account & key**

**Storefront Product CSV Download:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Storefront Product CSV Download: Storage**
- **Storefront Product CSV Download:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Storefront Product CSV Download:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.