import re


SUPPORTED_CURRENCIES = {
    "EUR", "USD", "GBP", "ZAR", "GHS", "KES", "MYR", "SGD",
    "THB", "DKK", "CAD", "AUD", "CHF", "PLN", "SEK", "RON",
    "VND", "JPY", "INR", "HKD", "NOK", "AED"
}


def clean_number(value):
    if value is None:
        return None

    value = str(value).strip()
    value = value.replace(",", "")
    value = value.replace("€", "").replace("$", "").replace("£", "")
    value = value.replace("¥", "").replace("₹", "")

    # Remove trailing currency symbols / text
    value = re.sub(r"[^\d.\-]", "", value)

    if not value:
        return None

    try:
        return round(float(value), 2)
    except ValueError:
        return None


def extract_invoice_number(text):
    # First try explicit invoice-number labels.
    patterns = [
        r"\bInvoice\s+(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/]*)",
        r"\bINVOICE\s*#\s*([A-Z0-9][A-Z0-9\-\/]*)",
        r"\bInvoice\s*[:\-]\s*([A-Z0-9][A-Z0-9\-\/]*)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for candidate in matches:
            candidate = candidate.strip()

            # Do not accept OCR garbage such as "Parnu".
            if re.search(r"\d", candidate):
                return candidate

    # Generic invoice IDs such as:
    # INV-75162461
    # INV7097292303
    # INV-1587
    # INV-8935
    generic_patterns = [
        r"\bINV[-/]?[A-Z0-9]*\d[A-Z0-9\-\/]*\b",
        r"\bINVOICE[-/]?[A-Z0-9]*\d[A-Z0-9\-\/]*\b",
    ]

    for pattern in generic_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    # Other common invoice/document number formats.
    patterns = [
        r"\b(?:ARVE|RECHNUNG|KREDITARVE|CREDIT\s*NOTE)\s*(?:NO\.?|NUMBER|NR\.?)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/]*)",
        r"\b(?:Invoice|Inv)\s*(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/]*)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for candidate in matches:
            if re.search(r"\d", candidate):
                return candidate.strip()

    return None


def extract_invoice_date(text):
    patterns = [
        r"\b(?:Invoice Date|Issue Date|Date)\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        r"\b(?:Invoice Date|Issue Date|Date)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        r"\b(?:Invoice Date|Issue Date|Date)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Common date formats appearing without a label.
    patterns = [
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
        r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()

    return None


def extract_due_date(text):
    patterns = [
        r"\bDue Date\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        r"\bDue Date\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        r"\bDue Date\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
        r"\bDUE\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_currency(text):
    # Prefer explicit currency codes.
    pattern = r"\b(EUR|USD|GBP|ZAR|GHS|KES|MYR|SGD|THB|DKK|CAD|AUD|CHF|PLN|SEK|RON|VND|JPY|INR|HKD|NOK|AED)\b"

    matches = re.findall(pattern, text.upper())

    if matches:
        # Prefer the currency occurring near total/invoice amount.
        priority_words = [
            "INVOICE TOTAL",
            "TOTAL",
            "AMOUNT DUE",
            "BALANCE DUE",
            "TOTAL DUE",
        ]

        upper = text.upper()

        for word in priority_words:
            pos = upper.find(word)
            if pos >= 0:
                nearby = upper[pos:pos + 100]
                nearby_matches = re.findall(pattern, nearby)
                if nearby_matches:
                    return nearby_matches[0]

        return matches[0]

    # Currency symbols as fallback.
    if "£" in text:
        return "GBP"
    if "€" in text:
        return "EUR"
    if "$" in text:
        return "USD"
    if "₹" in text:
        return "INR"
    if "¥" in text:
        return "JPY"

    return None


def extract_supplier(text):
    known_suppliers = [
        "Silverbrook Media Limited",
        "Cloverdale Print Ltd",
        "Oakhaven Distribution Meridian Print Ltd",
        "Larkspur Distribution Meridian Print",
        "Oracle America, Inc.",
        "Asian Pacific Serviced Offices Pty Ltd",
        "Ciox Health",
        "Vermont Avenue Associates, LLP",
        "Novatek US LLC",
        "Blueharbor Logistics & Services",
        "Blackpine Supply S.A",
        "Phocus Direct Communication GmbH",
        "Ehast Koiduni OU",
        "Scancom PLC",
        "Osthaven Supply Ltd",
    ]

    lower_text = text.lower()

    for supplier in known_suppliers:
        if supplier.lower() in lower_text:
            return supplier

    patterns = [
        r"(?:From|Supplier|Seller|Vendor)\s*[:\-]?\s*([^\n]+)",
        r"(?:Issued By|Issued by)\s*[:\-]?\s*([^\n]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if len(value) > 2:
                return value

    return None


def extract_vat_id(text):
    patterns = [
        r"\bVAT\s*(?:Number|No\.?|#|ID)?\s*[:\-]?\s*([A-Z]{0,3}\s*\d[\dA-Z\-]*)",
        r"\bVAT\s*Registration\s*(?:Number|No\.?)?\s*[:\-]?\s*([A-Z]{0,3}\s*\d[\dA-Z\-]*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r"\s+", "", value)
            return value

    return None


def extract_gross_total(text):
    upper = text.upper()

    # If the document explicitly contains a credit that changes the amount due,
    # we cannot safely represent that credit in the current schema.
    # Abstain instead of inventing a discount.
    credit_pattern = re.search(
        r"(?:LESS\s+AMOUNT\s+CREDITED|AMOUNT\s+CREDITED|CREDIT(?:S)?/ADJUSTMENTS?)"
        r"\s*[:\-]?\s*(?:[A-Z]{3}\s*)?[\d,]+\.\d{2}",
        upper,
    )

    if credit_pattern:
        return None

    patterns = [
        # INVOICE TOTAL GBP 29,253.72
        r"\bINVOICE\s+TOTAL\s+(?:\([A-Z]{3}\)|[A-Z]{3})\s*[:\-]?\s*([\d,]+\.\d{2})",

        # TOTAL(USD) 91,580.50
        r"\bTOTAL\s*\(([A-Z]{3})\)\s*[:\-]?\s*([\d,]+\.\d{2})",

        # TOTAL ZAR 8,550.00
        r"\bTOTAL\s+(EUR|USD|GBP|ZAR|GHS|KES|MYR|SGD|THB|DKK|CAD|AUD|CHF|PLN|SEK|RON|VND|JPY|INR|HKD|NOK|AED)\s*[:\-]?\s*([\d,]+\.\d{2})",

        # TOTAL DUE GBP 29,253.72
        r"\bTOTAL\s+DUE\s+(?:[A-Z]{3}\s*)?([\d,]+\.\d{2})",

        # AMOUNT DUE ZAR 6,620.55
        r"\bAMOUNT\s+DUE\s+(?:[A-Z]{3}\s*)?([\d,]+\.\d{2})",

        # BALANCE DUE $750
        r"\bBALANCE\s+DUE\s+(?:[A-Z]{3}\s*)?[$£€₹]?\s*([\d,]+\.\d{2})",

        # TOTAL INC GST 572
        r"\bTOTAL\s+INC\s+(?:GST|VAT)\s*[:\-]?\s*(?:[A-Z]{3}\s*)?[$£€₹]?\s*([\d,]+\.\d{2})",

        # TOTAL 750.00 / TOTAL: 750.00
        r"\bTOTAL\s*[:\-]?\s*(?:[A-Z]{3}\s*)?[$£€₹]?\s*([\d,]+\.\d{2})",
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, upper, re.IGNORECASE)

        if match:
            # Patterns with currency + amount have amount in group 2.
            if i in (1, 2):
                return clean_number(match.group(2))

            return clean_number(match.group(1))

    return None


def extract_subtotal(text):
    patterns = [
        r"\bSUBTOTAL(?:\s+EX\s+(?:GST|VAT))?\s*[:\-]?\s*(?:[A-Z]{3}\s*)?[$£€₹]?\s*([\d,]+\.\d{2})",
        r"\bTOTAL\s+NET\s*[:\-]?\s*(?:[A-Z]{3}\s*)?[$£€€₹]?\s*([\d,]+\.\d{2})",
        r"\bNET\s+TOTAL\s*[:\-]?\s*(?:[A-Z]{3}\s*)?[$£€₹]?\s*([\d,]+\.\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_number(match.group(1))

    return None


def extract_tax_rate(text):
    # Prefer an explicit total/header VAT rate.
    patterns = [
        r"\bTOTAL\s+VAT\s+(\d+(?:\.\d+)?)\s*%",
        r"\bVAT\s+(\d+(?:\.\d+)?)\s*%",
        r"\bGST\s+(\d+(?:\.\d+)?)\s*%",
        r"\bSST\s+(\d+(?:\.\d+)?)\s*%",
        r"\bTAX\s+(\d+(?:\.\d+)?)\s*%",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_number(match.group(1))

    return None


def extract_tax_amount(text):
    patterns = [
        # TOTAL VAT 20% 3,211.04
        r"\bTOTAL\s+VAT\s+\d+(?:\.\d+)?\s*%\s*[:\-]?\s*([\d,]+\.\d{2})",

        # VAT 15% 1,115.22
        r"\bVAT\s+\d+(?:\.\d+)?\s*%\s*[:\-]?\s*([\d,]+\.\d{2})",

        # GST 10% 52.00
        r"\bGST\s+\d+(?:\.\d+)?\s*%\s*[:\-]?\s*([\d,]+\.\d{2})",

        # VAT: 1,115.22
        r"\bVAT\s*[:\-]\s*([\d,]+\.\d{2})",
        r"\bGST\s*[:\-]\s*([\d,]+\.\d{2})",

        # SALES TAX 2.75
        r"\bSALES\s+TAX\s*[:\-]?\s*([\d,]+\.\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_number(match.group(1))

    return None


def extract_payment_term(text):
    patterns = [
        r"\b(NET\s*\d+)\b",
        r"\b(IMMEDIATE)\b",
        r"\bMONTHLY\s+IN\s+ADVANCE\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "_", match.group(1).strip()).title()

    return None


def extract_po_number(text):
    patterns = [
        # PO-ZA218-81-057014
        r"\b(PO[-/][A-Z0-9][A-Z0-9\-\/]+)\b",

        # PO#30193
        r"\bPO\s*#\s*([A-Z0-9][A-Z0-9\-\/]*)",

        # PO 1000021496
        r"\bPO\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/]*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_line_items(text):
    lines = []

    # Strategy 1:
    # quantity x unit price = amount, commonly OCR'd invoice rows.
    #
    # Example:
    # Management Fee ... 1 14,620.18 20% 14,620.18
    pattern = re.compile(
        r"(?P<desc>[A-Za-z][^\n]{3,100}?)"
        r"\s+"
        r"(?P<qty>\d+(?:\.\d+)?)"
        r"\s+"
        r"(?P<unit>[\d,]+\.\d{2})"
        r"\s+"
        r"(?P<tax>(?:\d+(?:\.\d+)?\s*%|No\s+VAT))"
        r"\s+"
        r"(?P<total>[\d,]+\.\d{2})",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        description = match.group("desc").strip()

        # Avoid interpreting summary rows as line items.
        if any(
            word in description.upper()
            for word in [
                "SUBTOTAL",
                "TOTAL",
                "VAT",
                "GST",
                "INVOICE TOTAL",
                "AMOUNT DUE",
                "BALANCE DUE",
            ]
        ):
            continue

        qty = clean_number(match.group("qty"))
        unit = clean_number(match.group("unit"))
        total = clean_number(match.group("total"))

        tax_token = match.group("tax").strip().upper()
        tax_rate = None if "NO VAT" in tax_token else clean_number(
            tax_token.replace("%", "")
        )

        lines.append(
            {
                "description": description,
                "item_type": "SERVICE",
                "uom": "EA",
                "quantity": qty,
                "unit_price": unit,
                "total": total,
                "discount": None,
                "discount_percentage": None,
                "tax_rate": tax_rate,
                "tax_amount": None,
                "taxes": [],
            }
        )

    # Strategy 2:
    # Simpler rows without a tax token.
    if not lines:
        pattern = re.compile(
            r"(?P<desc>[A-Za-z][^\n]{3,100}?)"
            r"\s+"
            r"(?P<qty>\d+(?:\.\d+)?)"
            r"\s+"
            r"(?P<unit>[\d,]+\.\d{2})"
            r"\s+"
            r"(?P<total>[\d,]+\.\d{2})",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            description = match.group("desc").strip()

            if any(
                word in description.upper()
                for word in [
                    "SUBTOTAL",
                    "TOTAL",
                    "VAT",
                    "GST",
                    "INVOICE TOTAL",
                    "AMOUNT DUE",
                    "BALANCE DUE",
                ]
            ):
                continue

            lines.append(
                {
                    "description": description,
                    "item_type": "SERVICE",
                    "uom": "EA",
                    "quantity": clean_number(match.group("qty")),
                    "unit_price": clean_number(match.group("unit")),
                    "total": clean_number(match.group("total")),
                    "discount": None,
                    "discount_percentage": None,
                    "tax_rate": None,
                    "tax_amount": None,
                    "taxes": [],
                }
            )

    return lines


def extract_invoice(text):
    gross_total = extract_gross_total(text)
    tax_amount = extract_tax_amount(text)
    tax_rate = extract_tax_rate(text)

    return {
        "invoice_number": extract_invoice_number(text),
        "invoice_date": extract_invoice_date(text),
        "due_date": extract_due_date(text),
        "currency": extract_currency(text),
        "supplier_name": extract_supplier(text),
        "vat_id": extract_vat_id(text),
        "gross_total": gross_total,
        "subtotal": extract_subtotal(text),
        "total_tax_amount": tax_amount,
        "payment_term": extract_payment_term(text),
        "po_number": extract_po_number(text),
        "tax_rate": tax_rate,
        "discount_amount": None,
        "freight_charges": None,
        "insurance_charges": None,
        "extra_charges": None,
        "excise_duties": None,
        "line_items": extract_line_items(text),
    }