# inventory.py — Allocation Spec

Implement `allocate(stock, request) -> dict` in `inventory.py`.

## Signature

```python
def allocate(stock: dict[str, int], request: dict[str, int]) -> dict[str, int]
```

## Behavior

`allocate` distributes available stock across a product request:

1. Returns a dict `sku -> allocated_qty`.
2. A sku missing from `stock` is **omitted** from the result (not zero).
3. When `request[sku] > stock[sku]`, allocate only what is available
   (partial allocation — never more than stock).
4. Requested quantities of **0 or less are omitted** from the result.
5. Stock entries not present in `request` are ignored.
6. The returned dict may be empty if nothing can be allocated.
7. Do not mutate the `stock` or `request` inputs.
