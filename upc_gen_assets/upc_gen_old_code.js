/**********************
 * CONFIG
 **********************/
const SUPABASE_URL =
  "https://oeyhqicugdqhxahxfdfg.supabase.co";

const DEFAULT_BUCKET = "labels";

const DEFAULT_TEMPLATE =
  "1FnBC2gCEarFpVHmCa707Vczn4b-I---fZenyFaeslIU";

/**********************
 * HTTP ENTRY
 **********************/
function doPost(e) {
  let tempFileId = null;

  try {
    const props =
      PropertiesService.getScriptProperties();

    const body = JSON.parse(
      e?.postData?.contents || "{}"
    );

    const expected =
      props.getProperty("API_TOKEN");

    if (
      expected &&
      body.token !== expected
    ) {
      return jsonOut(
        {
          status: "unauthorized",
          message: "Invalid API token."
        },
        401
      );
    }

    const title = String(
      body.title || ""
    ).trim();

    const productId = String(
      body.productId || ""
    ).trim();

    const sku = String(
      body.sku || ""
    ).trim();

    const upc = String(
      body.upc || ""
    ).trim();

    const size = String(
      body.size || ""
    ).trim();

    const msrp = toNumberOrNull(
      body.msrp
    );

    if (!/^\d{12}$/.test(upc)) {
      return jsonOut(
        {
          status: "error",
          message: "UPC must be 12 digits."
        },
        400
      );
    }

    if (!productId) {
      return jsonOut(
        {
          status: "error",
          message: "productId is required."
        },
        400
      );
    }

    const formatQuery = objectToQuery(
      body.barcodeFormat
    );

    const data = {
      title,
      productId,
      sku,
      upc,
      msrp,
      size,
      format: formatQuery
    };

    const mode = String(
      body.mode || "upload"
    ).toLowerCase();

    const slideTemplateId =
      body.slide_template_id ||
      DEFAULT_TEMPLATE;

    const bucket =
      body.supabase_bucket ||
      DEFAULT_BUCKET;

    /*
     * Default Supabase path:
     *
     * {productId}/{upc}.pdf
     */
    const path =
      body.supabase_path ||
      defaultPath(productId, upc);

    const result =
      createAndExportLabel({
        ...data,
        slideTemplateId
      });

    const pdfBlob = result.pdfBlob;
    tempFileId = result.tempFileId;

    if (mode === "inline") {
      const b64 =
        Utilities.base64Encode(
          pdfBlob.getBytes()
        );

      safeTrash(tempFileId);
      tempFileId = null;

      return jsonOut(
        {
          status: "success",
          mode: "inline",
          filename: `${upc}.pdf`,
          contentType: "application/pdf",
          pdf_base64: b64,
          title,
          productId,
          sku,
          upc,
          size,
          msrp
        },
        200
      );
    }

    const url = uploadToSupabase(
      pdfBlob,
      bucket,
      path
    );

    safeTrash(tempFileId);
    tempFileId = null;

    return jsonOut(
      {
        status: "success",
        mode: "upload",
        url,
        filePath: path,
        filename: `${upc}.pdf`,
        bucket,
        title,
        productId,
        sku,
        upc,
        size,
        msrp
      },
      200
    );
  } catch (err) {
    if (tempFileId) {
      safeTrash(tempFileId);
    }

    return jsonOut(
      {
        status: "error",
        message: String(
          err && err.message
            ? err.message
            : err
        ),
        stack: String(
          err && err.stack
            ? err.stack
            : ""
        )
      },
      500
    );
  }
}

/**********************
 * CORE BUILD STEPS
 **********************/
function createAndExportLabel({
  title,
  productId,
  sku,
  upc,
  msrp,
  size,
  slideTemplateId,
  format
}) {
  const barcodeBlob =
    fetchBarcodeBlob(
      upc,
      format
    );

  /*
   * Timestamp is used only for the temporary
   * Google Slides copy.
   */
  const copy = DriveApp
    .getFileById(slideTemplateId)
    .makeCopy(
      `Label_${upc}_${Date.now()}`
    );

  const tempFileId = copy.getId();

  const pres =
    SlidesApp.openById(tempFileId);

  const slide =
    pres.getSlides()[0];

  const formattedMsrp =
    Number.isFinite(msrp)
      ? Number(msrp).toFixed(2)
      : "";

  const replacements = {
    "{{TITLE}}": title,
    "{{PRODUCT ID}}": productId,
    "{{SKU}}": sku,
    "{{SIZE}}": size,
    "{{MSRP}}": formattedMsrp
  };

  for (
    const [placeholder, value]
    of Object.entries(replacements)
  ) {
    slide.replaceAllText(
      placeholder,
      value == null
        ? ""
        : String(value)
    );
  }

  /*
   * Optional aliases make the product ID
   * replacement more tolerant if the template
   * placeholder is changed later.
   */
  slide.replaceAllText(
    "{{PRODUCT_ID}}",
    productId
  );

  slide.replaceAllText(
    "{{PRODUCTID}}",
    productId
  );

  replaceBarcodePlaceholder(
    slide,
    barcodeBlob
  );

  pres.saveAndClose();

  Utilities.sleep(750);

  const pdfBlob =
    exportSlideAsPdf(tempFileId)
      .setName(`${upc}.pdf`)
      .setContentType(
        "application/pdf"
      );

  return {
    pdfBlob,
    tempFileId
  };
}

/**********************
 * BARCODE
 **********************/
function fetchBarcodeBlob(
  upc,
  query
) {
  const barcodeUrl =
    formatUpcBarcodeUrl(
      upc,
      query
    );

  const response =
    UrlFetchApp.fetch(
      barcodeUrl,
      {
        method: "GET",
        followRedirects: true,
        muteHttpExceptions: true,
        headers: {
          "User-Agent": "Mozilla/5.0"
        }
      }
    );

  const code =
    response.getResponseCode();

  const headers =
    response.getHeaders();

  const contentType =
    headers["Content-Type"] ||
    headers["content-type"] ||
    "";

  if (
    code < 200 ||
    code >= 300
  ) {
    throw new Error(
      `Barcode image fetch failed: ` +
      `${code} - ` +
      response.getContentText()
    );
  }

  if (
    !String(contentType)
      .toLowerCase()
      .includes("image")
  ) {
    throw new Error(
      `Barcode URL did not return an image. ` +
      `Content-Type: ${contentType}. ` +
      `Response: ${response.getContentText()}`
    );
  }

  return response
    .getBlob()
    .setName(`${upc}.png`);
}

function replaceBarcodePlaceholder(
  slide,
  barcodeBlob
) {
  const placeholder =
    "{{BARCODE}}";

  const found =
    findTextElementOnSlide(
      slide,
      placeholder
    );

  if (!found) {
    throw new Error(
      `Could not find ${placeholder} ` +
      `placeholder in slide template. ` +
      `Make sure the placeholder text is ` +
      `exactly ${placeholder} and is inside ` +
      `a normal text box.`
    );
  }

  const element = found.element;

  const left =
    element.getLeft();

  const top =
    element.getTop();

  const width =
    element.getWidth();

  const height =
    element.getHeight();

  element.remove();

  slide
    .insertImage(barcodeBlob)
    .setLeft(left)
    .setTop(top)
    .setWidth(width)
    .setHeight(height);
}

/**********************
 * PLACEHOLDER SEARCH
 **********************/
function findTextElementOnSlide(
  slide,
  searchText
) {
  const elements =
    slide.getPageElements();

  for (const element of elements) {
    const found =
      findTextElementRecursive(
        element,
        searchText
      );

    if (found) {
      return found;
    }
  }

  return null;
}

function findTextElementRecursive(
  element,
  searchText
) {
  const type =
    element.getPageElementType();

  if (
    type ===
    SlidesApp.PageElementType.SHAPE
  ) {
    const shape =
      element.asShape();

    try {
      const text = shape
        .getText()
        .asString();

      if (
        normalizeText(text).includes(
          normalizeText(searchText)
        )
      ) {
        return {
          element: shape
        };
      }
    } catch (_) {}
  }

  if (
    type ===
    SlidesApp.PageElementType.GROUP
  ) {
    const group =
      element.asGroup();

    const children =
      group.getChildren();

    for (const child of children) {
      const found =
        findTextElementRecursive(
          child,
          searchText
        );

      if (found) {
        return found;
      }
    }
  }

  if (
    type ===
    SlidesApp.PageElementType.TABLE
  ) {
    const table =
      element.asTable();

    for (
      let row = 0;
      row < table.getNumRows();
      row++
    ) {
      for (
        let column = 0;
        column < table.getNumColumns();
        column++
      ) {
        const cell =
          table.getCell(
            row,
            column
          );

        try {
          const text = cell
            .getText()
            .asString();

          if (
            normalizeText(text).includes(
              normalizeText(searchText)
            )
          ) {
            return {
              element
            };
          }
        } catch (_) {}
      }
    }
  }

  return null;
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\s+/g, "")
    .replace(/\u200B/g, "")
    .replace(/\uFEFF/g, "")
    .trim();
}

/**********************
 * PDF EXPORT
 **********************/
function exportSlideAsPdf(
  presentationId
) {
  const pres =
    SlidesApp.openById(
      presentationId
    );

  const slideId = pres
    .getSlides()[0]
    .getObjectId();

  const exportUrl =
    `https://docs.google.com/presentation/d/` +
    `${presentationId}/export/pdf` +
    `?format=pdf&pageid=${slideId}`;

  const response =
    UrlFetchApp.fetch(
      exportUrl,
      {
        method: "GET",
        headers: {
          Authorization:
            `Bearer ${ScriptApp.getOAuthToken()}`
        },
        muteHttpExceptions: true
      }
    );

  const code =
    response.getResponseCode();

  const text =
    response.getContentText();

  if (
    code < 200 ||
    code >= 300
  ) {
    throw new Error(
      `Google Slides PDF export failed: ` +
      `${code} - ${text}`
    );
  }

  return response
    .getBlob()
    .setContentType(
      "application/pdf"
    );
}

/**********************
 * SUPABASE UPLOAD
 **********************/
function uploadToSupabase(
  blob,
  bucket,
  path
) {
  const key =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        "SUPABASE_SERVICE_ROLE_KEY"
      );

  if (!key) {
    throw new Error(
      "Missing SUPABASE_SERVICE_ROLE_KEY " +
      "in Script Properties."
    );
  }

  const encodedBucket =
    encodeURIComponent(bucket);

  const encodedPath =
    encodeStoragePath(path);

  const uploadUrl =
    `${SUPABASE_URL}/storage/v1/object/` +
    `${encodedBucket}/${encodedPath}` +
    `?upsert=true`;

  const response =
    UrlFetchApp.fetch(
      uploadUrl,
      {
        method: "PUT",
        headers: {
          apikey: key,
          Authorization:
            `Bearer ${key}`,
          "Content-Type":
            blob.getContentType() ||
            "application/pdf",
          "x-upsert": "true"
        },
        payload: blob.getBytes(),
        muteHttpExceptions: true
      }
    );

  const code =
    response.getResponseCode();

  const text =
    response.getContentText();

  if (
    code < 200 ||
    code >= 300
  ) {
    throw new Error(
      `Supabase upload failed: ` +
      `${code} - ${text}`
    );
  }

  return (
    `${SUPABASE_URL}/storage/v1/object/public/` +
    `${encodedBucket}/${encodedPath}` +
    `?t=${Date.now()}`
  );
}

/**********************
 * PATH HELPERS
 **********************/
function defaultPath(
  productId,
  upc
) {
  const folder =
    sanitizePathPart(productId);

  return `${folder}/${upc}.pdf`;
}

function sanitizePathPart(value) {
  return (
    String(value || "")
      .trim()
      .replace(/[^\w\- ]+/g, "_")
      .replace(/\s+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "") ||
    "UNKNOWN"
  );
}

function encodeStoragePath(path) {
  return String(path)
    .split("/")
    .map(
      part =>
        encodeURIComponent(part)
    )
    .join("/");
}

/**********************
 * BARCODE URL HELPERS
 **********************/
function objectToQuery(params) {
  const parts =
    Object.entries(params || {})
      .filter(([, value]) => {
        return (
          value !== "" &&
          value !== null &&
          value !== undefined
        );
      })
      .map(([key, value]) => {
        return (
          `${encodeURIComponent(key)}=` +
          `${encodeURIComponent(
            String(value)
          )}`
        );
      });

  return parts.length
    ? `?${parts.join("&")}`
    : "";
}

function formatUpcBarcodeUrl(
  upc,
  query
) {
  return (
    `https://barcodeapi.org/api/a/` +
    `${encodeURIComponent(upc)}` +
    `${query || ""}`
  );
}

/**********************
 * GENERAL HELPERS
 **********************/
function toNumberOrNull(value) {
  if (
    value === "" ||
    value === null ||
    value === undefined
  ) {
    return null;
  }

  /*
   * Supports numeric values as well as
   * strings such as "$98.00".
   */
  const normalized = String(value)
    .replace(/[$,\s]/g, "");

  const number =
    Number(normalized);

  return Number.isFinite(number)
    ? number
    : null;
}

function safeTrash(fileId) {
  try {
    DriveApp
      .getFileById(fileId)
      .setTrashed(true);
  } catch (_) {}
}

function jsonOut(
  obj,
  statusCode
) {
  return ContentService
    .createTextOutput(
      JSON.stringify({
        ok:
          statusCode >= 200 &&
          statusCode < 300,
        statusCode,
        ...obj
      })
    )
    .setMimeType(
      ContentService.MimeType.JSON
    );
}