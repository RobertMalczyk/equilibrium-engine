# RPG Persona Dynamics — MVP cast (personas, traits, relation graph)

> Calibration targets + the cast for the "same soup, three situations" demo. A **connected small
> community** (a frontier watch-fort), not isolated archetypes: one event can touch several people
> (perpetrator / target / witness) on the **relation graph**. The player is simply another `AgentId`
> entering these relations.
>
> **Trait values are calibration targets, not literals** — here we freeze the **qualitative profile**
> (directions) and the **relation seed**; the numbers come out of the harness (spec §16). Mechanics:
> `spec_v1.md`.
>
> **Scope of multi-character behavior:** "they influence each other" in the MVP = a **shared, scripted
> event timeline touching multiple personas** (one event → several streams). Live autonomous
> multi-agency (NPC actions in real time becoming other characters' events) is stage 2; the
> architecture supports it (Relations per `AgentId`).

## MVP traits (frozen)

The set = exactly the `Traits` type from spec §3, all in [0..1]. Adding a trait = a deliberate change (§14):

`reactivity` · `patience` · `base_self_control` · `need_for_control` · `pride` ·
`novelty_seeking` · `threat_sensitivity` · `trust_disposition` · `gratitude` · `stoicism`.

## Cast (8)

- **Halgrim — watch sergeant** (`stoic_veteran`). Gravity and self-control; commands Branic, guards
  Cichy, respects Edda. Suppresses insults into `cold_response`. The antithesis of explosiveness.
- **Branic — recruit** (`curious_apprentice`). Bores fast on watch, reactive, weak control.
  Respect for Halgrim + slight resentment at his harshness.
- **Marta — cook** (`overworked_cook`). Cooks for everyone; **complaints about the food are booked on
  the complainer** (resentment toward grumblers). The "same soup" demo node — she both serves and
  reacts to criticism.
- **Edda — castellan** (`authority`). Issues orders to Marta and the staff; respected for competence.
  The authority node (the `repeated_command` test).
- **Wojslaw — noble guest** (`proud_noble`). Treats the staff with contempt, gives orders, easily
  slighted; the garrison tolerates him with resentment. Bursts where Halgrim suppresses.
- **Cichy — prisoner** (`resentful_prisoner`). Deep resentment and low trust/respect toward the guards
  **in the relations** (not in the traits). The bias-asymmetry node.
- **Welf — merchant stranded by the weather** (`bored_merchant`). Transactional, composed, high
  accumulation of boredom in idleness. Heavily exercises the proactive drive.
- **Lutek — wandering poet** (`curious_romantic`). Bores fastest and keeps firing new ideas (a dense
  series of `seek_stimulus`); turns insults into jokes — in the MVP: **does not burst**, thanks to
  stoicism + self_control (rewriting the valence into satisfaction = stage 2, §13).

### Trait profile (qualitative — directions, not numbers)

Legend: `↑↑` very high · `↑` high · `–` medium · `↓` low · `↓↓` very low.

| Persona | react | pat | bsc | nfc | pride | nov | thr | trust_d | grat | sto |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Halgrim (veteran)     | ↓  | ↑  | ↑↑ | –  | –  | ↓   | –  | –  | –  | ↑↑ |
| Branic (apprentice)   | ↑  | ↓  | ↓  | –  | –  | ↑↑  | –  | ↑  | –  | ↓  |
| Marta (cook)          | –  | –  | –  | ↓  | ↓  | –   | –  | –  | ↑  | –  |
| Edda (authority)      | ↓  | ↑  | ↑  | ↑↑ | ↑  | ↓   | –  | –  | –  | ↑  |
| Wojslaw (proud_noble) | ↑  | ↓  | ↓  | ↑  | ↑↑ | –   | –  | ↓  | ↓  | ↓  |
| Cichy (prisoner)      | ↑  | ↓  | ↓  | –  | –  | –   | ↑  | ↓↓ | ↓  | –  |
| Welf (merchant)       | ↓  | –  | –  | –  | –  | ↑   | –  | –  | –  | –  |
| Lutek (romantic)      | –  | ↓  | ↑* | ↓  | ↓  | ↑↑↑ | ↓  | ↑  | –  | ↑* |

`*` Lutek: high `bsc`/`sto` **selectively toward insults** (not global coldness). Additionally a **very
short** `boredom`/`satisfaction` half-life (a state parameter, not a trait) — see the note on `dt`.

`novelty_seeking` ordering (the key to the drive-frequency contrasts):
**Lutek ≫ Welf ≈ Branic > the rest > Halgrim.**

## Relation graph (`initial_relations` seed; directions, not numbers)

- **Edda → Marta / staff:** issues orders; Marta: respect↑ toward Edda. (authority)
- **Halgrim → Branic:** mentor/commands; Branic: respect↑ + slight resentment at his harshness; Halgrim: watchful.
- **Halgrim ↔ Edda:** mutual respect (competence).
- **Halgrim → Cichy:** guard/prisoner; Cichy: resentment↑↑, trust↓↓; Halgrim: low trust, duty.
- **Halgrim → Wojslaw:** tolerates with resentment, respect↓.
- **Wojslaw → staff (Marta et al.):** gives orders from above; low respect both ways; the garrison: resentment.
- **Cichy → Halgrim / Branic:** resentment↑, respect↓, trust↓↓ (the source of the bias asymmetry).
- **Marta:** cooks for everyone; **resentment is booked on the complainer** (e.g. Wojslaw's criticism → Marta.resentment[Wojslaw]↑).
- **Branic ↔ Lutek:** mild positive (both novelty-hungry).
- **Lutek → the rest:** neutral-warm; **indifferent to Wojslaw's tantrums** (low pride → no status game).
- **Welf → everyone:** transactional-neutral.

## Notes

- **`dt`:** Lutek has the shortest half-life in the cast, so via `dt = min(half-life)/10` **he sets the
  sampling step for the whole simulation** (a deliberate consequence). If too expensive — keep his
  half-life "fast, but not extreme".
- **Mapping the "same soup" demo:** **Marta** serves; the recipient changes the starting state. Lutek as
  recipient → a joke, never a burst; Wojslaw → grumbles/bursts (pride); a loyal guard → boredom rises,
  no burst. The same soup, different outputs — proof of "dynamics, not a `soup=anger` rule".
- **Obedience litmus (the second litmus, GATE 3 — command extension):** **Edda** is now modelled (she
  enters with `command`). The within-persona test uses the graph relations above: **Halgrim cooperates with
  Edda** (`Halgrim ↔ Edda: mutual respect`) and **refuses/cold-responds Wojslaw** (`Halgrim → Wojslaw:
  tolerates with resentment, respect↓`) — the SAME persona responding differently to two commanders, purely
  from `respect[source]`/`resentment[source]`. Halgrim's seed relations to Edda/Wojslaw are written from
  these directions in `data/personas/halgrim.yaml`.
