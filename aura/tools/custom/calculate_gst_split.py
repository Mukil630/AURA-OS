def calculate_gst_split(amount: float, gst_rate: float = 5.0) -> str:
    """Calculates taxable amount, CGST, and SGST split from gross amount."""
    taxable = amount / (1.0 + (gst_rate / 100.0))
    total_tax = amount - taxable
    cgst = total_tax / 2.0
    sgst = total_tax / 2.0
    return f"Gross: ₹{amount:.2f} | Taxable: ₹{taxable:.2f} | CGST: ₹{cgst:.2f} | SGST: ₹{sgst:.2f}"
