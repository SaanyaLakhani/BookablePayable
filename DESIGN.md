# Design — The Bookable Payable

## 1. What I eventually understood about the documents

The main challenge was not simply extracting fields from invoices. The documents contain different document types, bundled supporting pages, duplicate pages, reminders, estimates, credit notes and non-payable documents.

A document must first be interpreted to determine whether it represents a bookable payable. Extraction is performed only after this decision. This prevents values from unrelated pages or documents from being treated as invoice data.

I also found that OCR quality varies significantly across documents and countries. Therefore, the system is conservative: it uses explicit labels and document evidence where possible, and leaves fields blank rather than inventing values.

The ERP recomputation is also important. A payable is not correct merely because its printed total was extracted. Its structure must reproduce the ERP booking calculation.

## 2. What the system does for unseen documents

The pipeline processes every PDF independently.

First, PDF text is extracted using native PDF text when available and OCR for scanned pages. The document classifier then identifies likely document types such as invoice, credit memo, estimate, payment reminder, donation or customs document.

Non-payable document types are declined before extraction is converted into an ERP payable.

For payable candidates, the extractor looks for explicitly labelled invoice fields such as invoice number, dates, currency, totals, taxes, payment terms and purchase order numbers. Master-data matching is conservative: supplier, payment term and PO codes are populated only when there is evidence for a real master-data match.

The system also validates the extracted structure and sends the resulting payable through the provided ERP calculation. If the reconstructed ERP gross does not agree with the printed gross within the validation tolerance, the document is not emitted as a confident payable.

This approach is intended to generalize because it relies on document evidence and stable semantic labels rather than memorizing individual invoices or inventing missing values.

## 3. A document that could not be solved like the others

A useful example is INV-25.

It contains VAT-inclusive selling prices (`P.VENDA C/IVA`) and also shows the net amount and VAT total. The ERP schema requires a tax-exclusive unit price. Deriving a unit price by reversing the tax calculation would introduce a value that is not explicitly printed on the document.

The document is also duplicated as Original and Duplicado within the same PDF.

Rather than inventing tax-exclusive line prices or creating duplicate payables, the system declines this document. This follows the assignment rule that an unsupported correction is worse than leaving a document unresolved.