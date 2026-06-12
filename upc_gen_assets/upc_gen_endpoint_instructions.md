Build a production-ready Python service that replicates my existing Google Apps Script UPC label generator, but is optimized for speed and hosted on Render.

## Main goal

Replace the current Google Slides workflow with direct PDF generation in Python.

The service must:

- Generate the UPC label entirely in memory.
- Generate the UPC-A barcode locally.
- Not use Google Slides.
- Not call barcodeapi.org.
- Upload the generated PDF directly to Supabase Storage.
- Support returning the PDF directly or as base64.
- Be deployable to Render with minimal configuration.
- Be fast enough to generate many labels in succession.

Use:

- Python 3.12
- FastAPI
- Uvicorn
- ReportLab for PDF generation
- ReportLab barcode tools for UPC-A barcodes
- httpx for Supabase uploads
- Pydantic for request validation

## Request body

The single-label endpoint must accept this body:

```json
{
  "token": "API_TOKEN",
  "title": "RANCHER JACKET",
  "productId": "rec123456",
  "sku": "FA00001-SP26APL-XS",
  "upc": "840441527601",
  "msrp": 148,
  "size": "XS",
  "mode": "upload",
  "supabase_bucket": "labels",
  "supabase_path": "rec123456/840441527601.pdf"
}
```

The following fields should no longer be used:

- `style_number`
- `color`
- `description`
- `barcodeFormat`
- `slide_template_id`

The required label fields are:

- `title`
- `productId`
- `sku`
- `upc`
- `msrp`
- `size`

Normalize the values as follows:

```python
title = trimmed and uppercase
sku = trimmed and uppercase
size = trimmed and uppercase
productId = trimmed
upc = trimmed string
```

The UPC must remain a string so leading zeros are preserved.

Validate that the UPC contains exactly 12 digits.

Also validate its UPC-A check digit and return a useful 400 error when it is invalid.

## Authentication

Support authentication through either:

```http
Authorization: Bearer API_TOKEN
```

or:

```json
{
  "token": "API_TOKEN"
}
```

Read the expected token from the `API_TOKEN` environment variable.

Use constant-time comparison when validating the token.

Do not require authentication when `API_TOKEN` is empty in local development.

## Endpoints

Create these endpoints:

### Health check

```http
GET /health
```

Response:

```json
{
  "ok": true,
  "status": "healthy"
}
```

### Single label

```http
POST /labels
```

Generate one PDF containing one label.

Supported modes:

#### Upload mode

```json
{
  "mode": "upload"
}
```

Upload the PDF to Supabase Storage and return:

```json
{
  "ok": true,
  "statusCode": 200,
  "status": "success",
  "mode": "upload",
  "url": "PUBLIC_URL",
  "downloadUrl": "FORCED_DOWNLOAD_URL",
  "filePath": "rec123456/840441527601.pdf",
  "filename": "840441527601.pdf",
  "bucket": "labels",
  "title": "RANCHER JACKET",
  "productId": "rec123456",
  "sku": "FA00001-SP26APL-XS",
  "upc": "840441527601",
  "size": "XS",
  "msrp": 148
}
```

#### Inline base64 mode

```json
{
  "mode": "inline"
}
```

Return:

```json
{
  "ok": true,
  "statusCode": 200,
  "status": "success",
  "mode": "inline",
  "filename": "840441527601.pdf",
  "contentType": "application/pdf",
  "pdf_base64": "BASE64_DATA"
}
```

#### Direct download mode

```json
{
  "mode": "download"
}
```

Return the PDF response directly with:

```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="840441527601.pdf"
```

### Batch label endpoint

Create:

```http
POST /labels/batch
```

Request structure:

```json
{
  "token": "API_TOKEN",
  "title": "RANCHER JACKET CLAY PADDOCKS",
  "mode": "upload",
  "supabase_bucket": "labels",
  "variants": [
    {
      "productId": "rec123456",
      "title": "RANCHER JACKET",
      "sku": "FA00001-SP26APL-XS",
      "upc": "840441527601",
      "msrp": 148,
      "size": "XS"
    },
    {
      "productId": "rec123456",
      "title": "RANCHER JACKET",
      "sku": "FA00001-SP26APL-S",
      "upc": "840441527618",
      "msrp": 148,
      "size": "S"
    }
  ]
}
```

Generate a single combined PDF where each variant label is its own page.

Default combined path:

```text
combined/{NORMALIZED_TITLE}_UPC_LABELS.pdf
```

Normalize the filename by:

- Trimming whitespace.
- Converting to uppercase.
- Replacing spaces and special characters with underscores.
- Collapsing repeated underscores.
- Removing leading and trailing underscores.

Example:

```text
combined/RANCHER_JACKET_CLAY_PADDOCKS_UPC_LABELS.pdf
```

Support the same `upload`, `inline`, and `download` modes for batch generation.

## Label dimensions

Make the dimensions configurable through environment variables:

```env
LABEL_WIDTH_IN=3
LABEL_HEIGHT_IN=1.5
```

Default to a 3-inch by 1.5-inch label.

Each PDF page should be exactly one label.

## Label layout

Recreate a clean retail label similar to this structure:

```text
RANCHER JACKET                                 XS
rec123456
--------------------------------------------------

SKU                                           MSRP
FA00001-SP26APL-XS                         $148.00
--------------------------------------------------

                    UPC-A BARCODE
                    8 40441 52760 1
```

Layout requirements:

- White background.
- Black primary text.
- Light gray secondary text.
- Light gray divider lines.
- Bold title.
- Large bold size aligned to the top right.
- Product ID under the title in small gray text.
- SKU label and MSRP label in gray.
- SKU and price values in bold black.
- Barcode centered across the bottom.
- UPC digits displayed under the barcode.
- MSRP formatted with a dollar sign and exactly two decimal places.
- Long titles and SKUs must shrink or truncate safely rather than overflowing.
- Maintain balanced padding on all sides.

Create reusable layout helpers, including:

```python
fit_text(...)
ellipsize(...)
draw_label(...)
generate_pdf(...)
```

## Barcode generation

Use ReportLab’s local barcode generation.

Use a UPC-A barcode with human-readable digits.

Do not make any external barcode HTTP request.

The barcode should be a vector barcode inside the PDF rather than a raster image when possible.

Make sure the barcode:

- Fits within the label width.
- Has sufficient quiet zones.
- Is not stretched incorrectly.
- Remains scannable.
- Shows the UPC digits beneath it.

## Supabase upload

Read these environment variables:

```env
SUPABASE_URL=https://oeyhqicugdqhxahxfdfg.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_BUCKET=labels
API_TOKEN=
LABEL_WIDTH_IN=3
LABEL_HEIGHT_IN=1.5
HTTP_TIMEOUT_SECONDS=30
```

Upload using the Supabase Storage REST API.

Use:

```http
POST /storage/v1/object/{bucket}/{path}
```

Headers:

```http
apikey: SUPABASE_SERVICE_ROLE_KEY
Authorization: Bearer SUPABASE_SERVICE_ROLE_KEY
Content-Type: application/pdf
x-upsert: true
```

Existing PDFs at the same path must be overwritten.

Default single-label path:

```text
{sanitizedProductId}/{upc}.pdf
```

Default batch path:

```text
combined/{NORMALIZED_TITLE}_UPC_LABELS.pdf
```

Allow the request body to override the path using:

```json
{
  "supabase_path": "custom/path/file.pdf"
}
```

Return both a normal public URL and a forced-download URL.

Normal URL:

```text
{SUPABASE_URL}/storage/v1/object/public/{bucket}/{encodedPath}?t={timestamp}
```

Download URL:

```text
{SUPABASE_URL}/storage/v1/object/public/{bucket}/{encodedPath}?download={filename}&t={timestamp}
```

Encode each individual path segment correctly without encoding the `/` separators.

## Error handling

Use consistent JSON errors:

```json
{
  "ok": false,
  "statusCode": 400,
  "status": "error",
  "message": "UPC must be exactly 12 digits."
}
```

Add FastAPI exception handlers for:

- Validation errors
- HTTP exceptions
- Unexpected server errors

Do not return full stack traces in production responses.

Log stack traces server-side.

Return useful messages for:

- Missing product ID
- Invalid UPC length
- Invalid UPC characters
- Invalid UPC check digit
- Invalid request body
- Missing Supabase service role key
- Supabase upload failure
- Unsupported mode
- Empty variants array
- Too many variants

Set a configurable batch limit with:

```env
MAX_BATCH_LABELS=500
```

## Performance requirements

Optimize for speed:

- Generate PDFs entirely in memory with `io.BytesIO`.
- Do not create temporary files.
- Do not use Google APIs.
- Do not fetch barcode images.
- Reuse a shared `httpx.AsyncClient` instead of creating one for every upload.
- Create the shared HTTP client during FastAPI startup.
- Close it during shutdown.
- Run CPU-heavy ReportLab work through `asyncio.to_thread`.
- Use PDF page compression.
- Avoid unnecessary blocking operations.
- Avoid repeatedly loading fonts or static resources.
- Add reasonable request and response size limits where practical.

Do not add a task queue unless it is required.

The normal endpoint should complete synchronously and return the result in the same request.

## Project files

Create this complete project:

```text
.
├── app
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── labels.py
│   ├── storage.py
│   └── utils.py
├── tests
│   ├── test_upc.py
│   ├── test_paths.py
│   └── test_labels.py
├── requirements.txt
├── render.yaml
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

Do not put the entire application into one large file.

Separate:

- Environment configuration
- Pydantic models
- UPC validation
- PDF generation
- Supabase upload logic
- FastAPI routes
- General utilities

## Render deployment

Create `render.yaml` for a Render web service.

Use a start command similar to:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
```

Choose a worker count that is appropriate for Render and ReportLab.

Document that multiple workers increase memory use.

Include a Dockerfile using Python 3.12 slim.

Install only the operating-system packages actually needed.

Run the container as a non-root user.

Add a health check path:

```text
/health
```

## Requirements file

Pin compatible versions of:

- fastapi
- uvicorn
- reportlab
- httpx
- pydantic
- pydantic-settings
- pytest
- pytest-asyncio

Do not include unnecessary libraries.

## Tests

Add tests for:

- Valid UPC-A check digit
- Invalid UPC-A check digit
- UPC leading zeros
- Product path normalization
- Combined filename normalization
- PDF output begins with `%PDF`
- Single-label PDF has one page
- Batch PDF has one page per variant
- Long title does not crash generation
- Long SKU does not crash generation
- MSRP formatting
- Missing product ID
- Empty variants array
- Invalid authentication
- Upload path encoding

Use mocks for Supabase HTTP requests.

Tests must not upload real files.

## README

Include:

- Local setup
- Environment variables
- Render deployment steps
- Supabase bucket configuration
- Public bucket requirement
- Example curl request for each mode
- Example single-label request
- Example batch request
- How to test locally
- How to adjust label dimensions
- How to adjust the label layout
- Security warning about the Supabase service role key
- Explanation that the service role key must never be sent by the client
- Explanation that API authentication should be required in production

## Important implementation details

Keep the API compatible with my current workflow wherever possible.

The default single-label filename must remain:

```text
{upc}.pdf
```

The default single-label storage path must remain:

```text
{productId}/{upc}.pdf
```

The service should uppercase and trim the title, SKU, and size itself, even when the incoming workflow already does so.

Do not use Google Slides, LibreOffice, browser automation, Playwright, Puppeteer, HTML-to-PDF conversion, or any remote barcode service.

Generate the final complete codebase, not just examples or pseudocode.

After creating it:

1. Review every file for consistency.
2. Run the test suite.
3. Fix any failing tests.
4. Confirm that the application imports successfully.
5. Show the final directory structure.
6. Provide the exact Render environment variables I need to configure.