import json
import subprocess
import sys
from pathlib import Path


def validate_payable(payable):
    errors = []
    warnings = []

    required_fields = [
        "invoice_number",
        "invoice_date",
        "invoice_type",
        "currency",
        "supplier",
        "line_items",
    ]

    for field in required_fields:
        if field not in payable:
            errors.append(f"Missing field: {field}")

    if payable.get("invoice_type") not in [
        "INVOICE",
        "CREDIT_MEMO"
    ]:
        errors.append("Invalid invoice_type")

    if not payable.get("currency"):
        errors.append("Currency is missing")

    supplier = payable.get("supplier", {})

    if not supplier.get("name"):
        warnings.append("Supplier name is missing")

    line_items = payable.get("line_items", [])

    if not line_items:
        warnings.append("No line items found")

    for i, line in enumerate(line_items, start=1):

        if not line.get("description"):
            errors.append(
                f"Line {i}: missing description"
            )

        if line.get("quantity") is None:
            errors.append(
                f"Line {i}: missing quantity"
            )

        if line.get("unit_price") is None:
            errors.append(
                f"Line {i}: missing unit price"
            )

    # Basic line arithmetic check
    line_total = 0.0

    for line in line_items:

        quantity = line.get("quantity")

        unit_price = line.get("unit_price")

        if quantity is None or unit_price is None:
            continue

        try:
            line_total += float(quantity) * float(unit_price)

        except Exception:
            pass

    subtotal = payable.get("subtotal")

    if (
        subtotal is not None
        and line_items
    ):
        try:
            subtotal_value = float(subtotal)

            # Allow small rounding differences.
            if abs(line_total - subtotal_value) > 1.00:

                warnings.append(
                    f"Line total {line_total:.2f} "
                    f"differs from subtotal "
                    f"{subtotal_value:.2f}"
                )

        except Exception:
            pass

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def run_erp(payable, erp_path="erp.py"):

    temp_file = Path(
        "_validator_temp_payable.json"
    )

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                payable,
                f,
                indent=2,
                ensure_ascii=False
            )

        result = subprocess.run(
            [
                sys.executable,
                erp_path,
                str(temp_file)
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            return {
                "success": False,
                "error": result.stderr.strip()
            }

        try:
            erp_json = json.loads(
                result.stdout.strip()
            )

        except Exception:

            return {
                "success": False,
                "error": (
                    "ERP returned invalid JSON: "
                    + result.stdout.strip()
                )
            }

        return {
            "success": True,
            "result": erp_json
        }

    finally:

        if temp_file.exists():
            temp_file.unlink()


def reconcile(payable):

    validation = validate_payable(payable)

    if not validation["valid"]:

        return {
            "validation": validation,
            "erp": None,
            "reconciled": False
        }

    erp_result = run_erp(payable)

    if not erp_result.get("success"):

        return {
            "validation": validation,
            "erp": erp_result,
            "reconciled": False
        }

    erp_value = erp_result.get(
        "result",
        {}
    ).get("will_book_gross")

    printed_gross = payable.get(
        "gross_total"
    )

    # If we know the printed gross, compare it
    # against the ERP recomputation.
    if (
        erp_value is not None
        and printed_gross is not None
    ):

        try:

            difference = abs(
                float(erp_value)
                - float(printed_gross)
            )

            if difference > 1.00:

                validation["warnings"].append(
                    "ERP gross differs from "
                    f"printed gross by {difference:.2f}"
                )

                return {
                    "validation": validation,
                    "erp": erp_result,
                    "reconciled": False
                }

        except Exception:
            pass

    return {
        "validation": validation,
        "erp": erp_result,
        "reconciled": True
    }