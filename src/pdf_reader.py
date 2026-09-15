import re
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def ocr_page(page, dpi=300):
    """
    Render a PDF page at high resolution and OCR it.
    """
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    image = Image.frombytes(
        "RGB",
        [pix.width, pix.height],
        pix.samples
    )

    text = pytesseract.image_to_string(
        image,
        config="--psm 6"
    )

    return clean_text(text)


def read_pdf(pdf_path):
    """
    Read a PDF page-by-page.

    Strategy:
    1. Extract native PDF text.
    2. OCR every page as well.
    3. Combine both when useful.
    
    This is intentionally more robust for scanned invoices,
    image-heavy invoices and PDFs with incomplete embedded text.
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = []

    with fitz.open(pdf_path) as doc:

        for page_number, page in enumerate(doc, start=1):

            native_text = clean_text(
                page.get_text("text")
            )

            ocr_text = ""

            # OCR every page because many challenge PDFs contain
            # partial or misleading native text.
            try:
                ocr_text = ocr_page(page, dpi=300)
            except Exception as exc:
                print(
                    f"    OCR warning on page {page_number}: {exc}"
                )

            # If both sources exist, keep both.
            # Native text is generally more accurate for digitally
            # generated PDFs, while OCR recovers scanned content.
            if native_text and ocr_text:

                # Avoid huge duplication when OCR simply reproduces
                # the same native text.
                native_norm = re.sub(
                    r"\s+",
                    " ",
                    native_text.lower()
                ).strip()

                ocr_norm = re.sub(
                    r"\s+",
                    " ",
                    ocr_text.lower()
                ).strip()

                if (
                    native_norm in ocr_norm
                    or ocr_norm in native_norm
                ):
                    combined = native_text
                else:
                    combined = native_text + "\n" + ocr_text

            elif native_text:
                combined = native_text

            else:
                combined = ocr_text

            combined = clean_text(combined)

            pages.append(
                {
                    "page": page_number,
                    "text": combined,
                    "native_text": native_text,
                    "ocr_text": ocr_text,
                }
            )

    return pages