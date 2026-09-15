from pathlib import Path
import json
import re
from difflib import SequenceMatcher

try:
    import pymupdf as fitz
except ImportError:
    import fitz

import pytesseract
from PIL import Image


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
MASTER_DIR = ROOT_DIR / "master_data"


# ============================================================
# PDF READING + OCR
# ============================================================

def read_pdf(pdf_path):
    """
    Read native PDF text and OCR scanned/image pages.
    Returns one combined string for the whole PDF.
    """

    doc = fitz.open(str(pdf_path))
    page_texts = []

    for page in doc:
        native = page.get_text("text") or ""
        native = native.strip()

        # Render page for OCR
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)

        image = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

        ocr = pytesseract.image_to_string(
            image,
            config="--psm 6"
        ).strip()

        # Prefer native text when substantial, but append OCR
        # because some PDFs have only partial native text.
        if len(native) >= 80:
            combined = native
            if len(ocr) > 80 and ocr not in native:
                combined += "\n" + ocr
        else:
            combined = ocr if ocr else native

        page_texts.append(combined)

    doc.close()

    return "\n\n".join(page_texts)


def clean_text(text):
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ============================================================
# MASTER DATA
# ============================================================

def load_master(filename):
    path = MASTER_DIR / filename

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def records(data, possible_keys):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in possible_keys:
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def normalize(value):
    if value is None:
        return ""

    value = str(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def similarity(a, b):
    return SequenceMatcher(
        None,
        normalize(a),
        normalize(b)
    ).ratio()


def match_supplier(supplier_name):
    if not supplier_name:
        return {}

    data = load_master("suppliers.json")

    suppliers = records(
        data,
        ["suppliers", "data"]
    )

    best = None
    best_score = 0

    for supplier in suppliers:
        master_name = (
            supplier.get("name")
            or supplier.get("supplier_name")
            or supplier.get("vendor_name")
            or ""
        )

        if not master_name:
            continue

        score = similarity(supplier_name, master_name)

        if normalize(supplier_name) == normalize(master_name):
            score = 1.0

        if score > best_score:
            best_score = score
            best = supplier

    # Conservative matching — never invent a supplier code.
    if best is None or best_score < 0.82:
        return {}

    return {
        "supplier_id": best.get("supplier_id", ""),
        "name": (
            best.get("name")
            or best.get("supplier_name")
            or best.get("vendor_name")
            or ""
        ),
        "address": best.get("address", ""),
        "vat_id": (
            best.get("vat_id")
            or best.get("vat_number")
            or ""
        )
    }


def match_payment_term(term_text):
    if not term_text:
        return {}

    data = load_master("payment_terms.json")

    terms = records(
        data,
        ["payment_terms", "terms", "data"]
    )

    best = None
    best_score = 0

    for term in terms:

        candidates = [
            term.get("payment_term_id"),
            term.get("name"),
            term.get("description")
        ]

        aliases = term.get("aliases", [])

        if isinstance(aliases, list):
            candidates.extend(aliases)

        for candidate in candidates:
            if not candidate:
                continue

            score = similarity(term_text, candidate)

            if normalize(term_text) == normalize(candidate):
                score = 1.0

            if score > best_score:
                best_score = score
                best = term

    if best is None or best_score < 0.65:
        return {}

    return {
        "payment_term_id": (
            best.get("payment_term_id")
            or best.get("id")
            or best.get("name")
            or ""
        )
    }


def match_po(po_number):
    if not po_number:
        return {}

    data = load_master("po_master.json")

    pos = records(
        data,
        ["purchase_orders", "pos", "data"]
    )

    target = normalize(po_number)

    for po in pos:

        candidates = [
            po.get("po_id"),
            po.get("po_number"),
            po.get("id")
        ]

        for candidate in candidates:

            if candidate and normalize(candidate) == target:
                return {
                    "po_id": (
                        po.get("po_id")
                        or po.get("id")
                        or ""
                    ),
                    "po_number": (
                        po.get("po_number")
                        or po.get("po_id")
                        or ""
                    )
                }

    return {}


# ============================================================
# BASIC EXTRACTION HELPERS
# ============================================================

def first_match(text, patterns, flags=re.I | re.M):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = match.group(1).strip()
            if value:
                return value

    return ""


def number_from_text(value):
    if not value:
        return ""

    value = str(value).strip()

    # Remove currency symbols but keep digits, comma, dot and minus.
    value = re.sub(r"[^\d,.\-]", "", value)

    if not value:
        return ""

    # Handle common European format.
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "")
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")

    elif "," in value:
        parts = value.split(",")

        if len(parts[-1]) == 2:
            value = value.replace(".", "")
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")

    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

        return f"{number:.2f}".rstrip("0").rstrip(".")

    except Exception:
        return ""


def currency_from_text(text):
    upper = text.upper()

    # Strong currency labels first.
    currencies = [
        ("EUR", [r"\bEUR\b", r"\bEURO\b", r"€"]),
        ("GBP", [r"\bGBP\b", r"\bPOUND\b", r"£"]),
        ("USD", [r"\bUSD\b", r"\bUS DOLLAR\b", r"\$"]),
        ("CAD", [r"\bCAD\b"]),
        ("AUD", [r"\bAUD\b"]),
        ("SGD", [r"\bSGD\b"]),
        ("GHS", [r"\bGHS\b"]),
        ("ZAR", [r"\bZAR\b"]),
        ("KES", [r"\bKES\b"]),
        ("MYR", [r"\bMYR\b"]),
        ("THB", [r"\bTHB\b"]),
        ("DKK", [r"\bDKK\b"]),
        ("SEK", [r"\bSEK\b"]),
        ("PLN", [r"\bPLN\b"]),
        ("RON", [r"\bRON\b"]),
        ("VND", [r"\bVND\b"]),
        ("INR", [r"\bINR\b", r"₹"])
    ]

    for code, patterns in currencies:
        for pattern in patterns:
            if re.search(pattern, upper):
                return code

    return ""


def date_from_text(text, label_patterns):
    value = first_match(text, label_patterns)

    if not value:
        return ""

    value = value.strip(" .:-")

    # YYYY-MM-DD
    m = re.search(
        r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b",
        value
    )

    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # DD-MM-YYYY / DD.MM.YYYY / DD/MM/YYYY
    m = re.search(
        r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b",
        value
    )

    if m:
        return (
            f"{m.group(3)}-"
            f"{int(m.group(2)):02d}-"
            f"{int(m.group(1)):02d}"
        )

    # Month name.
    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12
    }

    m = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
        value
    )

    if m:
        month = months.get(m.group(2).lower())

        if month:
            return (
                f"{m.group(3)}-"
                f"{month:02d}-"
                f"{int(m.group(1)):02d}"
            )

    m = re.search(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})",
        value
    )

    if m:
        month = months.get(m.group(1).lower())

        if month:
            return (
                f"{m.group(3)}-"
                f"{month:02d}-"
                f"{int(m.group(2)):02d}"
            )

    return value


# ============================================================
# DOCUMENT TYPE
# ============================================================

def classify_document(text):
    t = text.lower()

    # Strong non-payable documents first.
    if any(x in t for x in [
        "customs consolidated invoice",
        "customs declaration",
        "customs valuation",
        "bill of entry",
        "customs invoice"
    ]):
        return "CUSTOMS_DOCUMENT"

    if any(x in t for x in [
        "estimate",
        "quotation",
        "quote for",
        "pro forma quotation"
    ]) and not any(x in t for x in [
        "amount due",
        "balance due",
        "total due",
        "invoice number",
        "tax invoice"
    ]):
        return "QUOTE"

    if any(x in t for x in [
        "donation form",
        "charitable contribution",
        "donation"
    ]) and "invoice" not in t:
        return "DONATION"

    if any(x in t for x in [
        "payment reminder",
        "payment reminder notice",
        "mahnung",
        "dunning notice"
    ]) and not any(x in t for x in [
        "invoice",
        "tax invoice",
        "credit note"
    ]):
        return "REMINDER"

    if any(x in t for x in [
        "delivery note",
        "delivery docket",
        "goods received"
    ]) and not any(x in t for x in [
        "invoice",
        "tax invoice",
        "credit note"
    ]):
        return "DELIVERY_NOTE"

    if any(x in t for x in [
        "credit note",
        "credit memo",
        "credit memorandum",
        "kreditarve",
        "gutschrift"
    ]):
        return "CREDIT_MEMO"

    if any(x in t for x in [
        "tax invoice",
        "invoice",
        "rechnung",
        "factura",
        "fatura",
        "invoice no",
        "invoice number",
        "inv no",
        "afregningsbilag"
    ]):
        return "INVOICE"

    return "UNKNOWN"


# ============================================================
# SUPPLIER / BUYER
# ============================================================

def extract_supplier(text):
    value = first_match(text, [
        r"(?:seller|supplier|vendor|from)\s*[:\-]\s*([^\n]+)",
        r"(?:issued by|issued from)\s*[:\-]\s*([^\n]+)"
    ])

    if value:
        return value[:150]

    # Try first meaningful company-looking line.
    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    for line in lines[:30]:

        low = line.lower()

        if any(x in low for x in [
            "invoice",
            "tax invoice",
            "credit note",
            "date",
            "customer",
            "bill to",
            "invoice no",
            "invoice number",
            "page "
        ]):
            continue

        if re.search(
            r"\b(gmbh|ltd|limited|llc|inc|corp|plc|pte|s\.a\.|srl|ou|ltda|services|supply|consult|company)\b",
            line,
            re.I
        ):
            return line[:150]

    return ""


def extract_buyer(text):
    return first_match(text, [
        r"(?:bill to|billed to|customer|client|buyer|invoice for)\s*[:\-]?\s*([^\n]+)"
    ])[:150]


# ============================================================
# TOTALS
# ============================================================

def extract_total(text):
    # Most reliable labels.
    patterns = [
        r"(?:amount due|balance due|total amount due|grand total|total due)\s*[:\-]?\s*[A-Z$€£₹]*\s*([\d.,]+)",
        r"(?:total incl\.?\s*(?:vat|tax)|total including tax|total inc\.?\s*(?:gst|vat|tax))\s*[:\-]?\s*[A-Z$€£₹]*\s*([\d.,]+)",
        r"(?:invoice total|total invoice|total)\s*[:\-]?\s*[A-Z$€£₹]*\s*([\d.,]+)"
    ]

    candidates = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = number_from_text(match.group(1))
            if value:
                candidates.append(value)

    if candidates:
        # Usually the last total-like value is the final payable amount.
        return candidates[-1]

    return ""


def extract_subtotal(text):
    return first_match(text, [
        r"(?:subtotal|sub-total|net total|net amount|total net)\s*[:\-]?\s*[A-Z$€£₹]*\s*([\d.,]+)"
    ])


def extract_tax_total(text):
    return first_match(text, [
        r"(?:total tax|tax total|vat total|gst total|sales tax)\s*[:\-]?\s*[A-Z$€£₹]*\s*([\d.,]+)",
        r"(?:vat|gst|sales tax)\s*[:\-]?\s*[A-Z$€£₹]*\s*([\d.,]+)"
    ])


# ============================================================
# TAX EXTRACTION
# ============================================================

def extract_taxes(text):
    taxes = []

    # Explicit tax lines such as:
    # VAT 20% 123.45
    # GST 9% 50
    patterns = [
        r"\b(VAT|GST|IVA|TVA|MwSt|Sales Tax)\b[^\n]{0,50}?(\d+(?:[.,]\d+)?)\s*%\s*[^\d\n]*([\d.,]+)",
        r"\b(VAT|GST|IVA|TVA|MwSt|Sales Tax)\b[^\n]{0,40}?[=:]\s*[^\d\n]*([\d.,]+)"
    ]

    for pattern in patterns:

        for match in re.finditer(pattern, text, re.I):

            groups = match.groups()

            if len(groups) == 3:

                tax_name = groups[0]
                rate = number_from_text(groups[1])
                amount = number_from_text(groups[2])

            else:

                tax_name = groups[0]
                rate = ""
                amount = number_from_text(groups[1])

            tax = {
                "tax_type": "VAT",
                "tax_name": tax_name.upper(),
                "tax_rate": rate,
                "tax_amount": amount,
                "tax_type_code": ""
            }

            if tax not in taxes:
                taxes.append(tax)

    return taxes[:10]


# ============================================================
# LINE ITEM EXTRACTION
# ============================================================

def extract_line_items(text):
    lines = []

    for raw in text.splitlines():

        line = raw.strip()

        if len(line) < 4:
            continue

        low = line.lower()

        # Skip obvious headers / totals.
        if any(x in low for x in [
            "subtotal",
            "grand total",
            "amount due",
            "balance due",
            "total tax",
            "tax total",
            "invoice number",
            "invoice date",
            "due date",
            "payment terms",
            "bill to",
            "ship to",
            "page ",
            "description quantity",
            "description qty"
        ]):
            continue

        # qty x unit price = total
        m = re.search(
            r"^\s*(\d+(?:[.,]\d+)?)\s+[^\d\n]*?\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s*$",
            line
        )

        if m:

            quantity = number_from_text(m.group(1))
            unit_price = number_from_text(m.group(2))
            total = number_from_text(m.group(3))

            if quantity and unit_price and total:

                lines.append({
                    "description": line,
                    "item_type": "GOODS",
                    "uom": "",
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total": total,
                    "discount": "",
                    "discount_percentage": "",
                    "tax_rate": "",
                    "tax_amount": "",
                    "taxes": []
                })

    # Avoid huge OCR noise.
    return lines[:100]


# ============================================================
# INVOICE NUMBER
# ============================================================

def extract_invoice_number(text):
    value = first_match(text, [
        r"(?:invoice\s*(?:no|number|#)|inv\.?\s*(?:no|number|#)|rechnung\s*(?:nr|no)|fatura\s*(?:no|n[ºo]))\s*[:#\-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})"
    ])

    if value:
        return value.strip()

    return ""


def extract_po(text):
    return first_match(text, [
        r"(?:PO|P\.O\.|purchase order|po number|order no\.?)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9./_-]+)"
    ])


def extract_payment_term(text):
    return first_match(text, [
        r"(?:payment terms|terms|terms of payment)\s*[:\-]\s*([^\n]+)",
        r"\b(Net\s*\d+)\b",
        r"\b(Immediate)\b"
    ])


# ============================================================
# MAIN EXTRACTION
# ============================================================

def extract_invoice(text, doc_type):

    invoice_number = extract_invoice_number(text)

    invoice_date = date_from_text(
        text,
        [
            r"(?:invoice date|invoice issued|issue date|date of invoice|date|invoice date)\s*[:\-]\s*([^\n]+)"
        ]
    )

    due_date = date_from_text(
        text,
        [
            r"(?:due date|payment due|due)\s*[:\-]\s*([^\n]+)"
        ]
    )

    supplier_name = extract_supplier(text)
    buyer_name = extract_buyer(text)

    po_number = extract_po(text)
    payment_term_text = extract_payment_term(text)

    currency = currency_from_text(text)

    gross_total = extract_total(text)
    subtotal = extract_subtotal(text)
    tax_total = extract_tax_total(text)

    taxes = extract_taxes(text)

    line_items = extract_line_items(text)

    supplier_match = match_supplier(supplier_name)
    payment_match = match_payment_term(payment_term_text)
    po_match = match_po(po_number)

    invoice_type = (
        "CREDIT_MEMO"
        if doc_type == "CREDIT_MEMO"
        else "INVOICE"
    )

    payable = {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "invoice_type": invoice_type,
        "currency": currency,

        "supplier": {
            "name": supplier_name,
            "supplier_id": supplier_match.get("supplier_id", ""),
            "address": supplier_match.get("address", ""),
            "vat_id": supplier_match.get("vat_id", "")
        },

        "buyer": {
            "company_code": "",
            "business_unit_code": "",
            "location_code": ""
        },

        "payment_term_id": payment_match.get(
            "payment_term_id",
            ""
        ),

        "po_number": (
            po_match.get("po_number")
            if po_match
            else po_number
        ),

        "po_id": po_match.get("po_id", ""),

        "gross_total": gross_total,
        "subtotal": subtotal,
        "total_tax_amount": tax_total,

        "header": {
            "discount_amount": "",
            "freight_charges": "",
            "insurance_charges": "",
            "extra_charges": "",
            "excise_duties": ""
        },

        "taxes": taxes,

        "line_items": line_items
    }

    return payable


# ============================================================
# DOCUMENT DECISION
# ============================================================

def process_pdf(pdf_path):

    text = clean_text(
        read_pdf(pdf_path)
    )

    doc_type = classify_document(text)

    # --------------------------------------------------------
    # Non-payable document types
    # --------------------------------------------------------

    if doc_type in [
        "CUSTOMS_DOCUMENT",
        "QUOTE",
        "DONATION",
        "REMINDER",
        "DELIVERY_NOTE",
        "UNKNOWN"
    ]:

        reasons = {
            "CUSTOMS_DOCUMENT": "Customs/commercial document is not an ERP payable invoice.",
            "QUOTE": "Quotation/estimate is not a payable invoice.",
            "DONATION": "Donation/charitable contribution document is not an ERP payable.",
            "REMINDER": "Payment reminder/dunning document is not the original payable.",
            "DELIVERY_NOTE": "Delivery note is not an invoice.",
            "UNKNOWN": "Document could not be reliably identified as a payable."
        }

        return {
            "file": Path(pdf_path).name,
            "payables": [],
            "declined": [{
                "doc_type": doc_type,
                "reason": reasons[doc_type]
            }]
        }

    # --------------------------------------------------------
    # Require actual payable evidence
    # --------------------------------------------------------

    has_invoice_signal = any(
        x in text.lower()
        for x in [
            "invoice",
            "tax invoice",
            "rechnung",
            "factura",
            "fatura",
            "afregningsbilag",
            "credit note",
            "credit memo",
            "kreditarve",
            "gutschrift"
        ]
    )

    has_amount_signal = any(
        x in text.lower()
        for x in [
            "amount due",
            "balance due",
            "total due",
            "grand total",
            "invoice total",
            "subtotal",
            "total incl",
            "total inc"
        ]
    )

    if not has_invoice_signal:

        return {
            "file": Path(pdf_path).name,
            "payables": [],
            "declined": [{
                "doc_type": doc_type,
                "reason": "No sufficiently reliable invoice/credit-document evidence."
            }]
        }

    if not has_amount_signal:

        # Some genuine invoices have only "Total" without "Amount Due".
        if not re.search(
            r"\btotal\b[^\n]{0,30}[\d.,]+",
            text,
            re.I
        ):

            return {
                "file": Path(pdf_path).name,
                "payables": [],
                "declined": [{
                    "doc_type": doc_type,
                    "reason": "Invoice identified but no reliable payable total was detected."
                }]
            }

    payable = extract_invoice(
        text,
        doc_type
    )

    # --------------------------------------------------------
    # Safety: don't emit an unusable payable
    # --------------------------------------------------------

    if not payable.get("gross_total"):

        return {
            "file": Path(pdf_path).name,
            "payables": [],
            "declined": [{
                "doc_type": doc_type,
                "reason": "Invoice detected but payable gross total could not be reliably extracted."
            }]
        }

    return {
        "file": Path(pdf_path).name,
        "payables": [payable],
        "declined": []
    }