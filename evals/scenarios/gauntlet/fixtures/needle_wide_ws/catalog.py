"""Product catalog."""


def sku(name: str) -> str:
    """Normalize a product name into a SKU."""
    return name.strip().lower().replace(" ", "_")
