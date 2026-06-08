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
)

RELATION_DIMS: tuple[str, ...] = ("trust", "respect", "resentment")

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


SemanticInputVector = dict[str, SemanticInput]  # from mapper (base)
EffectiveInputVector = dict[str, SemanticInput]  # after filters


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


# --- Snapshot (frozen view read by update/derived) --------------------------------


@dataclass(frozen=True)
class Snapshot:
    """Frozen copy of mutable state at the start of a tick (spec section 7, step 1)."""

    global_state: GlobalStateMap
    relations: Relations
    mode: Mode


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

    def freeze(self) -> Snapshot:
        """Deep-copied frozen snapshot (spec section 7, step 1)."""
        return Snapshot(
            global_state=dict(self.global_state),
            relations={src: dict(dims) for src, dims in self.relations.items()},
            mode=self.mode,
        )
