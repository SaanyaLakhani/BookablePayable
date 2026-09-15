import re


def normalize_text(text: str) -> str:
    """
    Normalize document text for classification.
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_document(text: str) -> dict:
    """
    Classify a document based on semantic/document signals.

    This is intentionally conservative.
    We do not want to call something payable just
    because it contains an amount.
    """

    text = normalize_text(text)

    # --------------------------------------------------
    # 1. Credit memo / credit note
    # --------------------------------------------------

    credit_keywords = [
        "credit note",
        "credit memo",
        "credit memorandum",
        "creditnota",
        "krediitarve",
        "gutschrift",
        "avoir",
    ]

    if any(keyword in text for keyword in credit_keywords):
        return {
            "doc_type": "CREDIT_MEMO",
            "payable_candidate": True,
            "confidence": "high",
            "reason": "Credit memo / credit note indicators found",
        }

    # --------------------------------------------------
    # 2. Estimate / quotation
    # --------------------------------------------------

    estimate_keywords = [
        "estimate",
        "quotation",
        "quote",
        "proforma",
        "pro forma",
        "kostenvoranschlag",
    ]

    if any(keyword in text for keyword in estimate_keywords):
        return {
            "doc_type": "ESTIMATE",
            "payable_candidate": False,
            "confidence": "high",
            "reason": "Estimate / quotation indicators found",
        }

    # --------------------------------------------------
    # 3. Payment reminder / dunning notice
    # --------------------------------------------------

    reminder_keywords = [
        "payment reminder",
        "reminder",
        "past due",
        "overdue",
        "dunning",
        "mahnung",
        "zahlungsaufforderung",
    ]

    if any(keyword in text for keyword in reminder_keywords):
        return {
            "doc_type": "PAYMENT_REMINDER",
            "payable_candidate": False,
            "confidence": "high",
            "reason": "Payment reminder indicators found",
        }

    # --------------------------------------------------
    # 4. Donation / contribution request
    # --------------------------------------------------

    donation_keywords = [
        "donation",
        "charitable contribution",
        "contribution form",
        "donor",
    ]

    if any(keyword in text for keyword in donation_keywords):
        return {
            "doc_type": "DONATION",
            "payable_candidate": False,
            "confidence": "high",
            "reason": "Donation-related indicators found",
        }

    # --------------------------------------------------
    # 5. Customs / import documentation
    # --------------------------------------------------

    customs_keywords = [
        "customs",
        "customs invoice",
        "customs declaration",
        "import declaration",
        "commercial customs invoice",
        "tariff",
    ]

    if any(keyword in text for keyword in customs_keywords):
        return {
            "doc_type": "CUSTOMS_DOCUMENT",
            "payable_candidate": False,
            "confidence": "medium",
            "reason": "Customs/import document indicators found",
        }

    # --------------------------------------------------
    # 6. Invoice
    # --------------------------------------------------

    invoice_keywords = [
        "invoice",
        "tax invoice",
        "invoice no",
        "invoice number",
        "rechnung",
        "rechnungsnummer",
        "rechnungsdatum",
        "factura",
        "fatura",
        "arve",
        "afregningsbilag",
    ]

    if any(keyword in text for keyword in invoice_keywords):
        return {
            "doc_type": "INVOICE",
            "payable_candidate": True,
            "confidence": "high",
            "reason": "Invoice indicators found",
        }

    # --------------------------------------------------
    # 7. Unknown
    # --------------------------------------------------

    return {
        "doc_type": "UNKNOWN",
        "payable_candidate": False,
        "confidence": "low",
        "reason": "No strong document-type indicators found",
    }