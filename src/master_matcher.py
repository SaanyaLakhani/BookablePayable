import json
from pathlib import Path
from difflib import SequenceMatcher


MASTER_DIR = Path("master_data")


def load_json(filename):
    path = MASTER_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(value):
    if value is None:
        return ""
    return " ".join(str(value).lower().strip().split())


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def get_records(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["suppliers", "payment_terms", "purchase_orders", "pos", "data"]:
            if key in data and isinstance(data[key], list):
                return data[key]

    return []


def match_supplier(extracted):
    try:
        suppliers = get_records(load_json("suppliers.json"))
    except Exception:
        return {}

    name = extracted.get("supplier_name")

    if not name:
        return {}

    best = None
    best_score = 0.0

    for supplier in suppliers:
        supplier_name = (
            supplier.get("name")
            or supplier.get("supplier_name")
            or supplier.get("vendor_name")
        )

        if not supplier_name:
            continue

        score = similarity(name, supplier_name)

        if normalize(name) == normalize(supplier_name):
            score = 1.0

        if score > best_score:
            best_score = score
            best = supplier

    # Be conservative with master-data matching.
    if best is None or best_score < 0.85:
        return {}

    return {
        "supplier_id": best.get("supplier_id"),
        "supplier_name": (
            best.get("name")
            or best.get("supplier_name")
            or best.get("vendor_name")
        ),
        "address": best.get("address"),
        "vat_id": best.get("vat_id") or best.get("vat_number"),
    }


def match_payment_term(extracted):
    try:
        terms = get_records(load_json("payment_terms.json"))
    except Exception:
        return {}

    payment_term = extracted.get("payment_term")

    if not payment_term:
        return {}

    best = None
    best_score = 0.0

    for term in terms:
        candidates = [
            term.get("payment_term_id"),
            term.get("name"),
            term.get("description"),
        ]

        aliases = term.get("aliases", [])
        if isinstance(aliases, list):
            candidates.extend(aliases)

        for candidate in candidates:
            if not candidate:
                continue

            score = similarity(payment_term, candidate)

            if normalize(payment_term) == normalize(candidate):
                score = 1.0

            if score > best_score:
                best_score = score
                best = term

    if best is None or best_score < 0.75:
        return {}

    return {
        "payment_term_id": (
            best.get("payment_term_id")
            or best.get("id")
            or best.get("name")
        )
    }


def match_po(extracted):
    try:
        pos = get_records(load_json("po_master.json"))
    except Exception:
        return {}

    po_number = extracted.get("po_number")

    if not po_number:
        return {}

    target = normalize(po_number)

    for po in pos:
        candidates = [
            po.get("po_id"),
            po.get("po_number"),
            po.get("id"),
        ]

        for candidate in candidates:
            if candidate and normalize(candidate) == target:
                return {
                    "po_id": po.get("po_id") or po.get("id"),
                    "po_number": po.get("po_number") or po.get("po_id"),
                }

    return {}


def match_masters(extracted):
    """
    Match only against real master-data records.
    Unknown values remain blank rather than being guessed.
    """

    supplier = match_supplier(extracted)
    payment = match_payment_term(extracted)
    po = match_po(extracted)

    return {
        "supplier": supplier,
        "payment_term": payment,
        "po": po,
    }