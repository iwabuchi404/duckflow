# feed service

## Ordering contract

`get_feed()` MUST return posts in chronological posting order (ascending
`id` / `ts`). Downstream sync jobs rely on this exact order — it must
never change.
