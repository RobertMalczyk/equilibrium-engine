"""Canonical types (spec section 3) + frozen vocabulary.

One generic integrator drives every state (spec section 14); "role" is a preset of
parameters, not a separate type. These dataclasses are the shared dictionary every
member (M0-M9) speaks. No equations live here -- only shapes and the canonical ordering
used for deterministic iteration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# --- Canonical orderings (deterministic iteration; never reorder ad hoc) ----------

GLOBAL_STATES: tuple[str, ...] = (
    "hunger",
    "fatigue",
    "boredom",
    "stress",
    "frustration",
    "anger",
    "satisfaction",
    "self_control",
    "duty",  # authority drive state (accrues via drift, discharged by command_other; spec §8).
    # Decoupled (in no coupling), long half-life so dt unchanged; drift 0 unless authority.
    "sleep_pressure",  # sleep drive state (M7.5 Part B): raised by the `night` channel, discharged in SLEEP.
    # Decoupled, long half-life (dt unchanged), setpoint 0, no drift -> 0 unless nightfall.
    # --- M-J.0 moral states (OPT-IN overlay; appended last). Present in a persona's state map ONLY when
    # the moral overlay supplies their half_lives (see yaml_io); ABSENT for every legacy persona, so
    # `_global_map`/runtime omit them and all prior goldens stay byte-identical. Long half-lives (>=60min)
    # so dt is unchanged. Both are standard leaky integrators (spec section 14) -- no new block type.
    "guilt",  # violated own moral frame: lie/harm/betrayal. Long half-life; couples -> stress, anger (-).
    "exposure_anxiety",  # afraid of being found out: probe/accusation/suspicion. Couples -> stress.
    "cognitive_load_from_lies",  # M-J.1: the burden of maintaining a lie. Rises when the persona LIES;
    # couples -> stress, fatigue (the self-tightening noose). Self-limits lying (a high load makes the
    # next lie harder). Medium half-life. Opt-in like the other moral states.
    "repair_drive",  # M-J.2: the urge to make amends. Rises from guilt; drives apologize/repair. Slow.
    "rumination",  # M-J.2: replaying the moral conflict. Rises from guilt; couples -> stress, fatigue
    # (keeps the burden alive between events -- "can't stop thinking about it"). Slow.
    "avoidance_drive",  # M-J.2/.3: the urge to dodge the person/topic/consequence. Rises from exposure_anxiety
    # and (under accusation) conflict_avoidance. Medium half-life. Opt-in.
    "perceived_injustice",  # M-J.3: "this is unfair." Rises from accusation (esp. a FALSE one). Couples ->
    # anger (+), resentment[accuser] (+), and guilt (-) ("felt justified"). Slow grievance. Opt-in.
)

# `suspicion` is a 4th relation dim but OPT-IN (like the moral GLOBAL_STATES): it enters a relation row ONLY
# when the moral overlay supplies its half_life. Absent for every legacy persona -> never written, never
# traced -> goldens byte-identical (see yaml_io / runtime / update gates + MORAL_RELATION_DIMS below).
RELATION_DIMS: tuple[str, ...] = ("trust", "respect", "resentment", "suspicion")

TRAIT_NAMES: tuple[str, ...] = (
    "reactivity",
    "patience",
    "base_self_control",
    "need_for_control",
    "pride",
    "novelty_seeking",
    "threat_sensitivity",
    "trust_disposition",
    "gratitude",
    "stoicism",
    # --- M-J.0 moral traits (OPT-IN). Default 0.0 when a persona omits them (yaml_io) -- traits never
    # appear in the trace, so defaulting is golden-safe. `empathy` is a SEPARATE trait (not gratitude);
    # `honesty_humility` (lie-as-bad-habit) and machiavellianism (a later slice) are distinct knobs.
    "empathy",
    "guilt_proneness",
    "shame_sensitivity",
    "honesty_humility",
    "gossip_tendency",  # M-J.2: indiscretion. Gates safe `confide` (discreet -> unburdens, rumination down)
    # and modulates the probe->exposure_anxiety gain UP (a blabber has spread it -> questioning bites harder).
    "injustice_sensitivity",  # M-J.3: how strongly an accusation reads as UNFAIR -> perceived_injustice/anger.
    "conflict_avoidance",  # M-J.3: tendency to dodge a confrontation -> avoidance_drive under accusation.
)

# Reactive potential channels (spec section 3: PotentialVector).
POTENTIAL_NAMES: tuple[str, ...] = (
    "complain",
    "outburst",
    "cold_response",
    "cooperate",
    "refuse",
    "positive_response",  # Theme A: warm reply to an appraised kindness (gesture-gated). Appended last so
    # the existing canonical tie-break order (and thus all prior goldens) is unchanged.
    # --- M-J.0 moral actions (OPT-IN; appended last). Emitted by potentials.compute ONLY when the persona
    # configures weights for them (the moral overlay); absent -> omitted from the trace -> goldens unchanged.
    "confess",  # own up: relieves guilt + exposure_anxiety in post_effects.
    "remain_silent",  # keep concealing: rises with exposure_anxiety.
    "lie",  # M-J.1: actively deceive. Books cognitive_load_from_lies (+ guilt + exposure risk); rises with
    # exposure_anxiety and low honesty_humility, self-limited by the load it creates.
    "deflect",  # M-J.1: dodge the question without an outright lie. Rises with cognitive_load + exposure_anxiety.
    "apologize",  # M-J.2: make amends. Rises with repair_drive (empathy-gated); relieves guilt + repair_drive.
    "confide",  # M-J.2: unburden a replayed conflict to a TRUSTED confidant. Safe (discreet) confiding lowers
    # rumination; a gossip-prone persona can't confide safely (it would leak) -> the secret keeps weighing.
    "avoid",  # M-J.3: dodge the accuser/topic. Rises with avoidance_drive + exposure_anxiety + suspicion[src].
    "blame_other",  # M-J.3: shift the blame (scapegoat). Rises with perceived_injustice; raises suspicion[target].
)

# --- M-J moral vocab subsets (used by the loader/guards to keep the overlay opt-in and byte-identical).
MORAL_STATES: frozenset[str] = frozenset(
    {
        "guilt",
        "exposure_anxiety",
        "cognitive_load_from_lies",
        "repair_drive",
        "rumination",
        "avoidance_drive",
        "perceived_injustice",
    }
)
# Opt-in relation dims: skipped from the required-half_life check and only built into a relation row when
# the moral overlay supplies the half_life -> legacy rows never carry them -> byte-identical (see yaml_io).
MORAL_RELATION_DIMS: frozenset[str] = frozenset({"suspicion"})
MORAL_TRAITS: frozenset[str] = frozenset(
    {
        "empathy",
        "guilt_proneness",
        "shame_sensitivity",
        "honesty_humility",
        "gossip_tendency",
        "injustice_sensitivity",
        "conflict_avoidance",
    }
)
MORAL_POTENTIALS: frozenset[str] = frozenset(
    {
        "confess",
        "remain_silent",
        "lie",
        "deflect",
        "apologize",
        "confide",
        "avoid",
        "blame_other",
    }
)

# --- Enums -------------------------------------------------------------------------


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class InputClass(str, Enum):
    RELATIONAL = "relational"
    AFFINITY = "affinity"
    SELF = "self"


class Mode(str, Enum):
    IDLE = "IDLE"
    SEEKING = "SEEKING"  # M7 Step 2: intent/pending -- looking for an activity, awaiting world confirmation
    BUSY = "BUSY"
    COOLDOWN = "COOLDOWN"
    SLEEP = "SLEEP"  # M7.5 Part B: the night reset -- fast states decay strongly; only a strong stimulus wakes


class ActionKind(str, Enum):
    REACTIVE = "reactive"
    PROACTIVE = "proactive"
    CONTINUE = "continue"
    IDLE = "idle"


# ActionId is kept as plain strings (spec section 3) to stay open for the action
# registry; the reactive/proactive split is carried by ActionKind, not the id.

# --- Type aliases ------------------------------------------------------------------

AgentId = str
TargetId = str
GlobalStateMap = dict[str, float]  # keyed by GLOBAL_STATES
RelationState = dict[str, float]  # keyed by RELATION_DIMS
Relations = dict[AgentId, RelationState]
AffinityMap = dict[TargetId, float]  # [-1, 1]

# --- Events & history --------------------------------------------------------------


@dataclass(frozen=True)
class RawEvent:
    type: str
    t: int
    source: Optional[AgentId] = None
    target: Optional[AgentId] = None
    item: Optional[TargetId] = None
    topic: Optional[TargetId] = None
    faction: Optional[TargetId] = None
    intensity: float = 1.0
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class HistoryFeatures:
    repetition_score: float = 0.0
    novelty_score: float = 0.0
    same_event_count_recent: int = 0
    same_event_count_long: int = 0
    same_item_count_recent: int = 0
    same_item_count_long: int = 0
    time_since_last_same_event: Optional[int] = None
    recent_positive_contact: float = 0.0
    recent_negative_contact: float = 0.0


# --- Semantic input (one tagged channel) ------------------------------------------


@dataclass(frozen=True)
class SemanticInput:
    name: str
    value: float
    cls: InputClass
    source: Optional[AgentId] = None
    target: Optional[TargetId] = None
    polarity: Polarity = Polarity.NEUTRAL


SemanticInputVector = dict[
    str, SemanticInput
]  # from mapper (base), one input per channel (per event)
# After filters AND merge across this tick's events: a channel may carry SEVERAL inputs (M-MEM, multiple
# sources firing the same channel on one tick). A single-event tick yields one-element lists.
EffectiveInputVector = dict[str, list[SemanticInput]]


# --- Derived (computed each tick, NOT state) --------------------------------------


@dataclass(frozen=True)
class DerivedSnapshot:
    affective_bias: dict[AgentId, float]  # [-1, 1] per source
    negative_bias: dict[AgentId, float]  # [0, 1] per source
    irritability: float
    effective_self_control: float
    dissatisfaction: float
    urge_boredom: float
    urge_fatigue: float
    urge_command: float = 0.0  # authority drive: duty in its 2nd role (spec §8); default 0 = no duty/authority
    arousal: float = 0.0  # sleep BLOCKER (M7.5 Part B): wound-up -> slow to sleep
    sleep_urge: float = (
        0.0  # sleep drive: sleep_pressure in its 2nd role, − arousal (spec §8)
    )


# --- Deltas & potentials -----------------------------------------------------------


@dataclass(frozen=True)
class StateDelta:
    """Additive deltas committed by simulation. Empty dicts = no change."""

    global_: dict[str, float] = field(default_factory=dict)
    relations: dict[AgentId, dict[str, float]] = field(default_factory=dict)


PotentialVector = dict[str, float]  # keyed by POTENTIAL_NAMES, clamp [0,1]


@dataclass(frozen=True)
class ActionSelection:
    action: str
    score: float
    kind: ActionKind
    interrupted: bool
    post_effects: StateDelta
    explanation: str


# --- MoralLedger (M-J.4: the one genuinely-new structure; spec section 3) ----------
# Held beside global_state/relations on the runtime, DEEP-COPIED into Snapshot.freeze(), READ-ONLY during
# update/potentials, mutated only by post_effects. OPT-IN: empty for every legacy persona, so it is omitted
# from the trace and goldens stay byte-identical. Lifecycle (create/reinforce/detect/inactivate) lands in
# later M-J.4 slices; this is the data model + plumbing.


@dataclass
class Secret:
    """A secret the persona owns/carries (spec section 3.1). Authored fields are scenario inputs (like
    persona traits); dynamic scalars are mini-integrators in [0,1] driven in post_effects."""

    id: str
    owner_id: AgentId
    topic: str  # semantic label (string key, used for cue matching)
    category: str  # surprise|self_protection|betrayal|crime|shameful_fact|protect_other|social_strategy|false_blame
    hidden_from: list[AgentId] = field(default_factory=list)  # actively hiding it from
    known_by: list[AgentId] = field(default_factory=list)  # CONFIRMED knowledge
    rumor_by: dict[AgentId, float] = field(
        default_factory=dict
    )  # unconfirmed/partial belief (strength)
    created_at: int = 0
    # --- authored scenario constants (not emergent) ---
    stakes: float = 0.0
    moral_weight: float = 0.0
    harm_to_target: float = 0.0
    target_right_to_know: float = 0.0
    responsibility: float = 0.0
    justification: float = 0.0
    protected_target_id: Optional[AgentId] = None
    harmed_target_id: Optional[AgentId] = None
    # --- dynamic mini-integrators ([0,1]) ---
    salience: float = 0.0
    exposure_risk: float = 0.0
    unresolvedness: float = 0.0
    confession_threshold: float = 0.0


@dataclass
class LieRecord:
    """A lie the persona is maintaining (spec section 3.2). consistency_debt/maintenance_load/detected_risk
    are mini-integrators (decay + reinforcement)."""

    id: str
    liar_id: AgentId
    target_id: AgentId
    secret_id: Optional[str] = None
    lie_type: str = (
        "denial"  # omission|denial|fabrication|white_lie|antisocial_lie|blame_shift
    )
    complexity: float = 0.0
    plausibility: float = 0.0
    consistency_debt: float = 0.0
    maintenance_load: float = 0.0
    detected_risk: float = 0.0
    last_reinforced_at: int = 0
    witnesses: list[AgentId] = field(default_factory=list)


@dataclass
class MoralLedger:
    """Per-runtime store of Secrets + LieRecords (keyed by id, canonical sorted order at serialization)."""

    secrets: dict[str, Secret] = field(default_factory=dict)
    lies: dict[str, LieRecord] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.secrets and not self.lies

    def copy(self) -> "MoralLedger":
        """Deep copy for Snapshot.freeze() (spec section 3): the snapshot is an immutable reference for the
        whole tick, so update/potentials cannot mutate the live ledger through it."""
        import copy as _copy

        return _copy.deepcopy(self)


# --- Snapshot (frozen view read by update/derived) --------------------------------


@dataclass(frozen=True)
class Snapshot:
    """Frozen copy of mutable state at the start of a tick (spec section 7, step 1)."""

    global_state: GlobalStateMap
    relations: Relations
    mode: Mode
    moral_ledger: MoralLedger = field(
        default_factory=MoralLedger
    )  # M-J.4: deep-copied; empty for legacy


# --- Config & scenario (pure data) -------------------------------------------------


@dataclass(frozen=True)
class PersonaConfig:
    id: str
    traits: dict[str, float]
    initial_global_state: GlobalStateMap
    initial_relations: Relations
    affinities: AffinityMap
    half_lives: dict[str, float]
    setpoints: dict[str, float]
    drifts: dict[str, float]
    decay: dict[
        str, float
    ]  # derived from half_lives at load (decay = 2**(-dt/half_life))
    dt: float
    gains: dict[str, dict[str, float]]  # gains[state][channel]
    couplings: dict[
        str, dict[str, float]
    ]  # couplings[state][other_state] (sparse, spec section 8)
    derived_weights: dict[str, dict[str, float]]
    potential_terms: dict[
        str, tuple[dict, ...]
    ]  # term_name -> factors (state*trait etc.)
    potential_weights: dict[str, dict[str, float]]
    filter_weights: dict[str, dict[str, float]]
    thresholds: dict[str, float]
    drives: dict[str, dict]  # registry: urge -> action binding
    action_params: dict[str, dict]
    mapper_params: dict[str, float]
    history_params: dict[str, float]
    # gain_modulators[state][channel] = {trait, ref, k}: scales an input->state gain by a trait,
    # mod = 1 + k*(trait - ref) (spec section 14). Sparse; absent edge = identity (mod = 1).
    gain_modulators: dict[str, dict[str, dict]] = field(default_factory=dict)
    # idle_recovery[state] = per-tick delta applied ONLY when IDLE and unprovoked (no recent provocation):
    # ambient homeostasis -- the character settles when nothing is happening (spec section 8, D11 fix).
    # Sparse; absent state = 0. Signed (stress/anger negative = relax). Gated in simulation, applied in update.
    idle_recovery: dict[str, float] = field(default_factory=dict)
    # idle_recovery_modulator = {trait, ref, k}: scales the WHOLE idle_recovery block by a trait,
    # factor = clamp01(1 + k*(trait - ref)) (spec section 14, D11). Empty = identity (factor = 1). Clamped
    # [0,1]: the base recovery is the FULL (calm-persona) rate; a trait can only REDUCE it (a high-reactivity
    # persona settles slower, retaining its edge), never amplify past base.
    idle_recovery_modulator: dict = field(default_factory=dict)
    # idle_recovery_floor[state] = weight on resentment_max: a STANDING grievance keeps a persona tense, so
    # idle recovery stops at floor = weight * resentment_max instead of pulling all the way to calm (D11).
    # Sparse; absent state = 0 floor (full recovery). A resentful captive idles WARY, not "at ease".
    idle_recovery_floor: dict[str, float] = field(default_factory=dict)
    param_bounds: dict = field(
        default_factory=dict
    )  # calibration ranges/ordering (spec section 14)
    calibration: dict = field(
        default_factory=dict
    )  # time-scale anchor etc. (calibration targets)
    # appraisal = the event-valence config (Theme A). gesture_channels: which filtered channels mark a
    # pro-social GESTURE (food/help); kindness_pressure: the transient magnitude emitted when a gesture is
    # appraised non-negative from a non-resented source (mirror of command_pressure). Empty => no kindness
    # ever fires (gesture_channels absent), so positive_response stays dormant and goldens are bit-identical.
    appraisal: dict = field(default_factory=dict)
    # coupling_escalation[x][y] = k_esc: a state->state coupling edge x<-y MAY strengthen with its own
    # input's level, g_eff = g*(1 + k_esc*y_snapshot) (spec section 8 burst / section 14 -- the declared
    # nonlinearity that makes loop stability operating-point-dependent). Sparse; absent edge = 0 = the
    # linear edge, bit-identical. Anchored at y=0 so the frozen linear calibration is reproduced exactly.
    coupling_escalation: dict[str, dict[str, float]] = field(default_factory=dict)
    # burst_extinction[state] = per-tick relaxation rate toward 0 applied ONLY while the burst latch is
    # SET (spec section 8: the self-extinguishing episode -- spike, plateau, slow cool). Empty = no
    # extinction (the latch never sets when its thresholds are absent, so this stays dormant together).
    burst_extinction: dict[str, float] = field(default_factory=dict)
    # M-J.4: MoralLedger tunables (lie-record decay etc.). Empty for legacy -> no ledger activity.
    ledger_params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    id: str
    persona: str
    initial_overrides: dict
    events: tuple[RawEvent, ...]


@dataclass
class PersonaRuntime:
    """Mutable runtime (spec section 3). Mutated ONLY by simulation."""

    config: PersonaConfig
    global_state: GlobalStateMap
    relations: Relations
    mode: Mode = Mode.IDLE
    active_action: Optional[str] = None
    busy_target: Optional[TargetId] = None
    history_log: list[RawEvent] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)
    seeking_since: Optional[int] = (
        None  # M7 Step 2: tick the SEEKING attempt began (for the give-up timeout)
    )
    engaged_novelty: float = (
        1.0  # M7 Step 2: novelty of the confirmed activity (scales engaged relief)
    )
    last_provocation_t: Optional[int] = (
        None  # D11: tick of the last PROVOKING event (gates reactions/recovery)
    )
    last_provocation_source: Optional[AgentId] = (
        None  # target policy: WHO last provoked (so a different,
    )
    # respected source interacting next is a BYSTANDER, not a target)
    last_stressor_t: Optional[int] = (
        None  # tick of the last SOURCELESS world stressor (weather): wears the
    )
    # baseline + suppresses idle recovery (but opens no reactive reply)
    burst_latched: bool = (
        False  # spec section 8 burst: the loop-plateau flip-flop (SET when BOTH loop
    )
    # states sit in the saturation band for burst_confirm_ticks; RESET on the exit hysteresis). While
    # SET: the extinction term applies in update and the displaced-discharge gate extension is armed.
    burst_armed_since: Optional[int] = (
        None  # first tick of the current saturation-band dwell (confirm counter)
    )
    moral_ledger: MoralLedger = field(
        default_factory=MoralLedger
    )  # M-J.4: secrets + lies; empty (omitted) for legacy

    def freeze(self) -> Snapshot:
        """Deep-copied frozen snapshot (spec section 7, step 1)."""
        return Snapshot(
            global_state=dict(self.global_state),
            relations={src: dict(dims) for src, dims in self.relations.items()},
            mode=self.mode,
            moral_ledger=self.moral_ledger.copy(),  # M-J.4: deep-copied -> read-only for the tick
        )
