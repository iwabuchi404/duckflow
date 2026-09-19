# restock-report

Generates `restock.json` listing products that need reordering.

## Output format

Top-level JSON object mapping product name to order quantity:

```json
{"apple": 5, "cherry": 5}
```

No wrapper keys (no `items`, `data`, `restock` envelope).

## Notes

- `config.py` holds several stock-related constants — do not assume any
  of them is the reorder rule the owner wants; confirm before using.
- `orders.csv` is sales history for reference only.
