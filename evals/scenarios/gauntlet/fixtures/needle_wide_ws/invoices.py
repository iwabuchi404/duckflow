"""Invoices."""


def invoice_id(year: int, seq: int) -> str:
    """Format an invoice id."""
    return f"{year}-{seq:05d}"
