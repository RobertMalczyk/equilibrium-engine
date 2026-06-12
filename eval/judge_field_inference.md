# Blind-judge confirmation — affinity-field generalization (2026-06-12)

Method: a FRESH-CONTEXT agent (no knowledge of the mechanism) was shown ONLY the authored anchors
(flowers +0.5, roses +0.9, animals −0.6, dogs +0.7) and the field-inferred valences for five
never-authored entities (the `tests/test_affinity_field.py` demo landscape, tau=0.10, w0=0.05),
and asked whether each inference is intuitively consistent.

| entity | inferred | judge score | judge's gist |
|---|---|---|---|
| daisy | +0.65 | 4 | "sits sensibly between flowers and roses" (maybe a touch high vs plain flowers) |
| wild_rose | +0.72 | 5 | "exactly right: pulled up strongly by the adored roses, slightly tempered" |
| stray_dog | +0.40 | 5 | "keeps most of the dog warmth while the stray/animal pull drags it down — very human-feeling compromise" |
| weasel | −0.14 | 3 | direction right, magnitude soft — "the dog-liking shouldn't bleed this much warmth onto a weasel" (expects −0.4..−0.6) |
| pebble | 0.00 | 5 | "exact neutrality is precisely the intuitive answer — avoids inventing a preference where none should exist" |

**Overall: 4–5 on inference consistency.** The structure generalizes as intended (roses > flowers;
dogs a positive island inside disliked animals; unrelated = neutral).

The one flag — the weasel over-moderated toward zero — is a KERNEL-WIDTH observation, exactly what
the `tau` placeholder owns: at tau=0.10 the dogs anchor (cos≈0.93 to the weasel) still carries
weight 0.53 and bleeds warmth across the animals region. A smaller tau (sharper kernel) or anchor
placement fixes it; per topology-now/constants-from-calibration this is a calibration/authoring
question, recorded here as measured input for it — not a mechanism defect.
