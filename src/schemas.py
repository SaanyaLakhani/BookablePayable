def empty_payable():
    return {
        "invoice_number": "",
        "invoice_date": "",
        "due_date": "",
        "invoice_type": "INVOICE",
        "currency": "",
        "supplier": {
            "name": "",
            "supplier_id": "",
            "address": "",
            "vat_id": ""
        },
        "buyer": {
            "company_code": "",
            "business_unit_code": "",
            "location_code": ""
        },
        "payment_term_id": "",
        "po_number": "",
        "po_id": "",
        "gross_total": "",
        "subtotal": "",
        "total_tax_amount": "",
        "header": {
            "discount_amount": "",
            "freight_charges": "",
            "insurance_charges": "",
            "extra_charges": "",
            "excise_duties": ""
        },
        "taxes": [],
        "line_items": []
    }


def build_payable(
    extracted,
    supplier_match=None,
    payment_match=None,
    po_match=None,
    tax_match=None,
    invoice_type="INVOICE"
):
    """
    Convert extracted document data into the required ERP
    autodraft structure.

    Important:
    - Never invent master-data codes.
    - Empty strings mean no reliable match.
    - Printed numeric values are preserved.
    """

    payable = empty_payable()

    # ---------------------------------------------------------
    # Header fields
    # ---------------------------------------------------------

    payable["invoice_number"] = (
        extracted.get("invoice_number") or ""
    )

    payable["invoice_date"] = (
        extracted.get("invoice_date") or ""
    )

    payable["due_date"] = (
        extracted.get("due_date") or ""
    )

    payable["invoice_type"] = invoice_type

    payable["currency"] = (
        extracted.get("currency") or ""
    )

    # ---------------------------------------------------------
    # Supplier
    # ---------------------------------------------------------

    payable["supplier"]["name"] = (
        extracted.get("supplier_name") or ""
    )

    payable["supplier"]["vat_id"] = (
        extracted.get("vat_id") or ""
    )

    if supplier_match:
        payable["supplier"]["supplier_id"] = (
            supplier_match.get("supplier_id", "")
        )

    # ---------------------------------------------------------
    # Payment term
    # ---------------------------------------------------------

    if payment_match:
        payable["payment_term_id"] = (
            payment_match.get("payment_term_id", "")
        )

    # ---------------------------------------------------------
    # PO
    # ---------------------------------------------------------

    payable["po_number"] = (
        extracted.get("po_number") or ""
    )

    if po_match:
        payable["po_id"] = (
            po_match.get("po_id", "")
        )

    # ---------------------------------------------------------
    # Totals
    # ---------------------------------------------------------

    payable["gross_total"] = extracted.get("gross_total")

    payable["subtotal"] = extracted.get("subtotal")

    payable["total_tax_amount"] = (
        extracted.get("total_tax_amount")
    )

    # ---------------------------------------------------------
    # Header charges / discounts
    # ---------------------------------------------------------

    payable["header"]["discount_amount"] = (
        extracted.get("discount_amount") or ""
    )

    payable["header"]["freight_charges"] = (
        extracted.get("freight_charges") or ""
    )

    payable["header"]["insurance_charges"] = (
        extracted.get("insurance_charges") or ""
    )

    payable["header"]["extra_charges"] = (
        extracted.get("extra_charges") or ""
    )

    payable["header"]["excise_duties"] = (
        extracted.get("excise_duties") or ""
    )

    # ---------------------------------------------------------
    # Tax
    # ---------------------------------------------------------

    tax_rate = extracted.get("tax_rate")
    tax_amount = extracted.get("total_tax_amount")

    if tax_rate is not None or tax_amount is not None:

        tax = {
            "tax_type": "",
            "tax_name": "",
            "tax_rate": (
                tax_rate if tax_rate is not None else ""
            ),
            "tax_amount": (
                tax_amount if tax_amount is not None else ""
            ),
            "tax_type_code": ""
        }

        # Only use a master-data tax match if one was
        # independently established.
        if tax_match:
            tax["tax_type"] = tax_match.get(
                "tax_type", ""
            )
            tax["tax_name"] = tax_match.get(
                "tax_name", ""
            )
            tax["tax_type_code"] = tax_match.get(
                "tax_type_code", ""
            )

        payable["taxes"] = [tax]

    # ---------------------------------------------------------
    # Line items
    # ---------------------------------------------------------

    payable["line_items"] = extracted.get(
        "line_items", []
    )

    return payable