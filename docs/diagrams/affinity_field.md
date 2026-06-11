# Affinity field — entity valence as a cosine-blended field over an embedding space

> Spec: §5 (affinity-FIELD subsection — the generalized affinity-table `lookup`), §13 (staging),
> §14 (the seam). Design of record: `Ideas/affinity_field_unification.md` (private overlay repo).
> Status: SPEC/DIAGRAM ONLY — implementation pending. Coordinates/anchors are AUTHORED config;
> `tau`, `w_0`, gain are calibration placeholders. Empty field = identity; explicitly-authored
> entries bypass the field entirely (exact-entry override) = bit-identical.

## 1. Control form

```text
                          FROZEN CONFIG (offline; embedding generation, if any,
                          happens at the perception seam and is CACHED here)
                ┌─────────────────────────────────────────────────────────────┐
                │  explicit table: entity → value          (today's entries)  │
                │  coordinates:    entity → x_e ∈ R³  (unit-normalized at     │
                │                  load; zero vector = hard config error)     │
                │  anchors:        a → (x_a, v_a)   sparse; v_a = scalar for  │
                │                  objects, sparse (v_trust,v_respect,        │
                │                  v_resentment) components for agents        │
                └──────────────────────┬──────────────────────────────────────┘
                                       │
 entity id ──► [ in explicit table? ]──┬── yes ──► value = table[e]   EXACT-ENTRY OVERRIDE
                                       │           (k=1: a specific authored judgment beats
                                       │            the generalized landscape; this is what
                                       │            makes the migration byte-exact)
                                       └── no:
                                  [ cos(x_e, x_a) ] ──► [ kernel exp((cos−1)/τ) ] ──► w_a
                                       │                       (weights computed ONCE per entity)
                                       ▼
                              ┌─────────────────────────────────────────────────────────┐
                              │  per declared component c:                              │
                              │     valence_c(e) = Σ w_a·v_a,c / (Σ w_a + w_0)          │
                              │  (kernel regression with a NEUTRAL PRIOR: far from      │
                              │   every anchor → Σw_a ≪ w_0 → valence ≈ 0 = neutral;    │
                              │   output clamp_signed)                                  │
                              └──────────────────────────┬──────────────────────────────┘
                                                         │ + debug log: contributing
                                                         │   anchors + cosine weights
                                                         ▼
                       filters.py resolver: factor = 1 + gain·sign·valence(e)
                                                         │
              ┌──────────────────────────────────────────┼──────────────────────────┐
              ▼ OBJECTS (stage 1, scalar v)              ▼ PEOPLE (A) (stage 2)     ▼ PEOPLE (B) (stage 3, target)
   feed-forward input gain                    SEEDS initial trust/respect/      persistent feed-forward PRIOR
   (backs the STATIC affinity                 resentment for a STRANGER         (the same per-dim blend) added
   table only — call site unmoved)            from the per-dim blend            alongside the learned relation

   SCOPE: the field backs STATIC authored tables only. The relation stage's dynamic per-source
   relation reads (and the betrayal nested-trust fetch) are live state — plain dict path, untouched.
   NO integrator, NO loop anywhere → pole/Jury discipline untouched (asserted + tested, incl. B).
```

## 2. Functional form (domain language)

```text
 The character does not keep a ledger with one row per thing in the world.
 Instead, their likes and dislikes are a LANDSCAPE: a few authored landmarks
 ("flowers +", "roses ++", "animals −", "dogs +", "snakes −−") pin the terrain,
 and everything else takes its value from where it STANDS in that landscape.
        │
        ├── a daisy he has never seen stands near "flowers"        → he likes it
        ├── a rose stands in the sub-region of flowers he adores   → he likes it MORE
        ├── a strange beast stands near "animals", far from "dogs" → he recoils
        ├── a thing far from every landmark                        → he simply doesn't care
        └── BUT the one specific rose his late wife planted has its OWN authored value —
            a specific judgment always beats the landscape          → exact-entry override
        │
        ▼
 PEOPLE stand in the landscape too — and a person is not one number:
   the landmarks for people carry trust / respect / resentment components, so
   (A) a stranger's FIRST impression is read off the landscape per dimension — "a new
       noble starts distrusted and resented, though grudgingly respected" — and from
       then on lived experience (the relation dynamics) takes over;
   (B, target) the landscape keeps whispering underneath the lived experience — an
       instinctive distaste for his kind that lingers even as I come to trust HIM.
        │
        ▼
 And every judgment stays explainable: "−0.31, because he stands 0.8-close to
 'snakes'(−0.8) and 0.3-close to 'pets'(+0.5)."
```

## 3. LIGHTHOUSE classification (done before build, per the idea note)

Checked against L1–L5 before implementation: the field is **deterministic** (pure arithmetic over
frozen config; any model-generated embeddings are offline, cached, never in the tick), **debuggable**
(anchor-contribution logging is a hard requirement, more explanatory than the dict it replaces),
**feed-forward only** (no new integrator/loop — the core control-system thesis and stability
discipline untouched), and **emergence-preserving** (people option C — replacing the relation
dynamics — is explicitly REJECTED; A/B keep visible behaviour driven by the state dynamics).
Believed L-safe; re-classify if implementation pressure pushes toward any in-tick model call or any
field→state feedback.

## 4. Staging & acceptance

| Stage | Scope | Gate (bit-identical before opt-in anchors) |
|---|---|---|
| 1 | field backs the affinity-table `lookup` for OBJECTS | empty field = identity → goldens byte-identical; existing `affinities` entries ride the EXACT-ENTRY OVERRIDE → byte-exact even with anchors populated; then roses/flowers + dogs/animals proximity demo + tests asserting the debug log explains each blend |
| 2 | PEOPLE (A): seed stranger relations from per-dim blends | existing seeded personas unaffected → goldens hold; a stranger's seeded dims match the blend (test) |
| 3 | PEOPLE (B): persistent per-dim prior | only after (A) validates; stability assert incl. the prior path |

New config (placeholders): `tau` (kernel temperature), `w_0` (neutral-prior weight), per-stage gain.
Authored (character/world design, NOT calibrated): coordinates, anchor placement, anchor valences
(scalar for objects, sparse per-dim components for agents).
Open question deliberately left to stage 1: one shared space for objects+people vs per-domain spaces
sharing the mechanism (the per-dim components make a shared space workable — an object anchor simply
declares no relation components).
