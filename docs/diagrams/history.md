# Block diagram — history (M2, history features)

> Pure, deterministic, combinational over the log (no dynamics) — an **I/O contract + a counting
> schematic**. Synchronized with `engine/history.py`. Counts and recency only; interprets NO semantics
> (the mapper turns these counts into `repetition`/`novelty` channels). Mutates nothing.

## I/O
`In:` log (past RawEvents) + current event + t + history_params. `Out:` HistoryFeatures.

## Counting (functional)

```
   over the log, for each past event:
     same_type? → same_event_count_long (+ recent if t−past.t ≤ recent_window), track last_same_t
     same_item? → same_item_count_long  (+ recent if within window)

   repetition_score = clamp01( same_item_count_recent / repetition_norm )     ─► mapper: repetition channel
   novelty_score    = clamp01( 1 − repetition_score )                          ─► mapper: novelty channel
   time_since_last_same_event = t − last_same_t   (or None)
```

Window sizes / normalizers come from `config.history_params` (recent_window, repetition_norm) — no
literals. `recent_positive_contact`/`recent_negative_contact` are placeholders (0.0) in MVP. The richer
short/medium/long/streak/novelty filter library (spec §9) is a stage-2 expansion.
