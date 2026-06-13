"""Loader + validation (M0).

In: YAML paths. Out: validated PersonaConfig / Scenario. Does parsing, schema validation,
defaults merge, and the time-scale reparametrization (dt and decay from half-lives,
spec section 2). Holds NO dynamics. Calibration values live in YAML; this module derives
``dt = min(half_life) / nyquist_factor`` and ``decay = 2 ** (-dt / half_life)``.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from engine.clamp import clamp01, clamp_signed
from engine.schema import (
    GLOBAL_STATES,
    RELATION_DIMS,
    TRAIT_NAMES,
    PersonaConfig,
    RawEvent,
    Scenario,
)

# Valid factor vocabularies for declarative potential terms (spec section 8).
_DERIVED_FACTORS = frozenset(
    {
        "irritability",
        "effective_self_control",
        "dissatisfaction",
        "urge_boredom",
        "urge_fatigue",
    }
)
_RELATION_AGG_FACTORS = frozenset({"trust_max", "respect_max", "resentment_max"})
# "Stateful" kinds: a term must carry at least one of these so personality (traits) alone
# can never trigger a reaction at zero emotion (invariant, spec section 8).
# Grounding kinds: a term needs >=1 of these so a trait can't fire a reaction alone. command_pressure
# (transient: 0 if no order) and relation_source (per-source relation read) are grounding too -- generic,
# reusable (relation_source also serves M5's promise/apology channels, not command-specific).
_STATEFUL_KINDS = frozenset(
    {"state", "derived", "relation_agg", "command_pressure", "relation_source"}
)


def _validate_factor(factor: dict, ctx: str) -> dict:
    kind = factor.get("kind")
    name = factor.get("name")
    if kind == "state":
        if name not in GLOBAL_STATES:
            raise ValueError(f"{ctx}: unknown state factor '{name}'")
    elif kind == "derived":
        if name not in _DERIVED_FACTORS:
            raise ValueError(f"{ctx}: unknown derived factor '{name}'")
    elif kind == "trait":
        if name not in TRAIT_NAMES:
            raise ValueError(f"{ctx}: unknown trait factor '{name}'")
    elif kind == "relation_agg":
        if name not in _RELATION_AGG_FACTORS:
            raise ValueError(f"{ctx}: unknown relation_agg factor '{name}'")
    elif kind in (
        "command_pressure",
        "kindness_pressure",
        "bystander_pressure",
        "refractory_pressure",
    ):
        name = None  # transient scalar; no name
    elif kind == "relation_source":
        if name not in RELATION_DIMS:
            raise ValueError(
                f"{ctx}: relation_source factor needs a relation dim (trust/respect/resentment), got '{name}'"
            )
    else:
        raise ValueError(
            f"{ctx}: factor kind must be state|derived|trait|relation_agg|command_pressure|kindness_pressure|bystander_pressure|refractory_pressure|relation_source, got '{kind}'"
        )
    return {
        "kind": kind,
        "name": name,
        "complement": bool(factor.get("complement", False)),
    }


def _load_potential_terms(raw: dict, ctx: str) -> dict[str, tuple[dict, ...]]:
    out: dict[str, tuple[dict, ...]] = {}
    for term_name, factors in dict(raw).items():
        if not factors:
            raise ValueError(
                f"{ctx}.potential_terms['{term_name}']: term needs >=1 factor"
            )
        parsed = [
            _validate_factor(dict(f), f"{ctx}.potential_terms['{term_name}']")
            for f in factors
        ]
        if not any(f["kind"] in _STATEFUL_KINDS for f in parsed):
            raise ValueError(
                f"{ctx}.potential_terms['{term_name}']: every term must carry at least one "
                f"state/derived/relation_agg factor (traits only MODULATE; spec section 8)"
            )
        out[term_name] = tuple(parsed)
    return out


def _load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: top-level YAML must be a mapping, got {type(data).__name__}"
        )
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` onto a copy of ``base`` (override wins on leaves)."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _require(d: dict, key: str, ctx: str) -> object:
    if key not in d:
        raise ValueError(f"{ctx}: missing required key '{key}'")
    return d[key]


def _derive_dt(half_lives: dict[str, float], nyquist_factor: float) -> float:
    if not half_lives:
        raise ValueError("half_lives empty: cannot derive dt")
    return min(half_lives.values()) / nyquist_factor


def _derive_decay(half_lives: dict[str, float], dt: float) -> dict[str, float]:
    # decay = 2 ** (-dt / half_life)  (spec section 2: decay = exp(-ln2 * dt / half_life))
    return {name: 2.0 ** (-dt / hl) for name, hl in half_lives.items()}


def load_persona(
    persona_path: str | Path,
    defaults_path: str | Path,
    param_overrides: dict | None = None,
) -> PersonaConfig:
    """Load + validate a PersonaConfig. ``param_overrides`` (the calibration param-injection
    seam, spec section 16.1) is deep-merged LAST onto the config dict, so dt/decay are
    re-derived from any overridden half_lives -- making the simulator a pure function of params."""
    defaults = _load_yaml(defaults_path)
    persona_raw = _load_yaml(persona_path)
    merged = _deep_merge(defaults, persona_raw)
    if param_overrides:
        merged = _deep_merge(merged, param_overrides)

    ctx = str(persona_path)
    persona_id = str(_require(merged, "id", ctx))

    # --- traits (validated + clamped) ---
    traits_in = dict(_require(merged, "traits", ctx))
    traits: dict[str, float] = {}
    for name in TRAIT_NAMES:
        if name not in traits_in:
            raise ValueError(f"{ctx}: missing trait '{name}'")
        traits[name] = clamp01(float(traits_in[name]))

    # --- time scales: half-lives -> dt -> decay ---
    half_lives = {
        k: float(v) for k, v in dict(_require(merged, "half_lives", ctx)).items()
    }
    for name in GLOBAL_STATES + RELATION_DIMS:
        if name not in half_lives:
            raise ValueError(f"{ctx}: missing half_life for '{name}'")
    tick_cfg = dict(_require(merged, "tick", ctx))
    nyquist_factor = float(_require(tick_cfg, "nyquist_factor", ctx + ".tick"))
    # Optional GLOBAL time-scale (default 1.0 = identity): scales ALL half_lives uniformly. Because
    # dt = min(half_life)/nyquist scales with them, every per-tick decay (2**(-dt/half_life)) is INVARIANT
    # -> the tick-by-tick trace is BIT-IDENTICAL; only the seconds a tick represents (dt) stretch. This is
    # the "keep every factor, make the whole clock slower" reparametrization: it turns the placeholder-fast
    # emotions (anger half-life 30s) into a believable day (e.g. time_scale 80 -> 40 min) WITHOUT touching
    # any relation, gain, threshold, or ordering. Default 1.0 keeps defaults.yaml + every golden unchanged;
    # the eval/story path opts in. The dt=min(half_life)/nyquist invariant (spec section 2) still holds exactly.
    time_scale = float(tick_cfg.get("time_scale", 1.0))
    if time_scale != 1.0:
        half_lives = {k: v * time_scale for k, v in half_lives.items()}
    dt = _derive_dt(half_lives, nyquist_factor)
    decay = _derive_decay(half_lives, dt)

    setpoints = {k: float(v) for k, v in dict(merged.get("setpoints", {})).items()}
    drifts = {k: float(v) for k, v in dict(merged.get("drifts", {})).items()}

    # --- initial state (clamped) ---
    init_global_in = dict(merged.get("initial_global_state", {}))
    initial_global_state = {
        name: clamp01(float(init_global_in.get(name, 0.0))) for name in GLOBAL_STATES
    }

    initial_relations: dict[str, dict[str, float]] = {}
    for src, dims in dict(merged.get("initial_relations", {})).items():
        initial_relations[str(src)] = {
            d: clamp01(float(dict(dims).get(d, 0.0))) for d in RELATION_DIMS
        }

    affinities = {
        str(k): clamp_signed(float(v))
        for k, v in dict(merged.get("affinities", {})).items()
    }

    # gains: {state: {channel: float}}, except the reserved 'relations' key which carries
    # relational-dim deposits nested one level deeper: {dim: {channel: float}} (see update.py).
    gains: dict[str, dict] = {}
    for s, ch in dict(merged.get("gains", {})).items():
        if s == "relations":
            gains[s] = {
                dim: {c: float(g) for c, g in dict(chs).items()}
                for dim, chs in dict(ch).items()
            }
        else:
            gains[s] = {c: float(g) for c, g in dict(ch).items()}
    couplings = {
        s: {o: float(g) for o, g in dict(edges).items()}
        for s, edges in dict(merged.get("couplings", {})).items()
    }
    # coupling_escalation[x][y] = k_esc on the existing edge x<-y (spec section 8 burst / section 14):
    # g_eff = g*(1 + k_esc*y). Sparse; each escalated edge MUST exist in couplings (the nonlinearity
    # rides a declared linear edge, never creates one).
    coupling_escalation: dict[str, dict[str, float]] = {}
    for s, edges in dict(merged.get("coupling_escalation", {})).items():
        for o, k in dict(edges).items():
            if couplings.get(str(s), {}).get(str(o)) is None:
                raise ValueError(
                    f"{ctx}.coupling_escalation['{s}']['{o}']: no such edge in couplings"
                )
            k = float(k)
            if k < 0.0:
                # a negative k_esc could flip the coupling's SIGN at high states (1 + k*y < 0) --
                # that is a different mechanism (saturation), not the declared escalation.
                raise ValueError(
                    f"{ctx}.coupling_escalation['{s}']['{o}']: k_esc must be >= 0 (got {k})"
                )
            coupling_escalation.setdefault(str(s), {})[str(o)] = k
    # burst_extinction[state] = per-tick relaxation rate toward 0 while the burst latch is SET (spec
    # section 8 burst). Sparse; dormant unless the latch thresholds are configured.
    burst_extinction: dict[str, float] = {}
    for s, v in dict(merged.get("burst_extinction", {})).items():
        if s not in GLOBAL_STATES:
            raise ValueError(f"{ctx}.burst_extinction: unknown state '{s}'")
        v = float(v)
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"{ctx}.burst_extinction['{s}']: rate must be in [0,1] (got {v})"
            )
        burst_extinction[str(s)] = v
    # idle_recovery[state] = per-tick delta applied only when IDLE and unprovoked (spec section 8, D11).
    # Sparse; validated against the state vocabulary. Signed (negative = relax toward calm).
    idle_recovery: dict[str, float] = {}
    for s, v in dict(merged.get("idle_recovery", {})).items():
        if s not in GLOBAL_STATES:
            raise ValueError(f"{ctx}.idle_recovery: unknown state '{s}'")
        idle_recovery[str(s)] = float(v)
    # idle_recovery_modulator = {trait, ref, k}: scales the idle_recovery block by a trait (spec section 14).
    idle_recovery_modulator: dict = {}
    irm = dict(merged.get("idle_recovery_modulator", {}))
    if irm:
        trait = str(_require(irm, "trait", f"{ctx}.idle_recovery_modulator"))
        if trait not in TRAIT_NAMES:
            raise ValueError(f"{ctx}.idle_recovery_modulator: unknown trait '{trait}'")
        idle_recovery_modulator = {
            "trait": trait,
            "ref": float(irm.get("ref", 0.5)),
            "k": float(irm.get("k", 0.0)),
        }
    # idle_recovery_floor[state] = weight on resentment_max (a standing grievance keeps a persona tense, D11).
    idle_recovery_floor: dict[str, float] = {}
    for s, v in dict(merged.get("idle_recovery_floor", {})).items():
        if s not in GLOBAL_STATES:
            raise ValueError(f"{ctx}.idle_recovery_floor: unknown state '{s}'")
        idle_recovery_floor[str(s)] = float(v)
    # gain_modulators[state][channel] = {trait, ref, k}: trait modulation of an input->state gain
    # (spec section 14). Sparse; absent = identity. Validated: the trait must exist.
    gain_modulators: dict[str, dict[str, dict]] = {}
    for s, chs in dict(merged.get("gain_modulators", {})).items():
        row: dict[str, dict] = {}
        for ch, m in dict(chs).items():
            m = dict(m)
            trait = str(_require(m, "trait", f"{ctx}.gain_modulators['{s}']['{ch}']"))
            if trait not in TRAIT_NAMES:
                raise ValueError(
                    f"{ctx}.gain_modulators['{s}']['{ch}']: unknown trait '{trait}'"
                )
            row[str(ch)] = {
                "trait": trait,
                "ref": float(m.get("ref", 0.5)),
                "k": float(m.get("k", 0.0)),
            }
        gain_modulators[str(s)] = row
    derived_weights = {
        k: {kk: float(vv) for kk, vv in dict(v).items()}
        for k, v in dict(_require(merged, "derived_weights", ctx)).items()
    }
    potential_terms = _load_potential_terms(merged.get("potential_terms", {}), ctx)
    potential_weights = {
        k: {kk: float(vv) for kk, vv in dict(v).items()}
        for k, v in dict(_require(merged, "potential_weights", ctx)).items()
    }
    # Every weighted term must be declared in potential_terms (no implicit features).
    for action, weights in potential_weights.items():
        for term_name in weights:
            if term_name not in potential_terms:
                raise ValueError(
                    f"{ctx}.potential_weights['{action}']: term '{term_name}' not in potential_terms"
                )
    filter_weights = {
        k: {kk: float(vv) for kk, vv in dict(v).items()}
        for k, v in dict(merged.get("filter_weights", {})).items()
    }
    thresholds = {
        k: float(v) for k, v in dict(_require(merged, "thresholds", ctx)).items()
    }
    # Burst-latch threshold set (spec section 8 burst): all-or-nothing, with a real hysteresis.
    # A partial set is a config MISTAKE (the latch would silently stay disabled), so it is rejected.
    _burst_keys = ("burst_enter.anger", "burst_enter.stress", "burst_exit")
    _present = [k for k in _burst_keys if k in thresholds]
    if _present and len(_present) != len(_burst_keys):
        missing = [k for k in _burst_keys if k not in thresholds]
        raise ValueError(
            f"{ctx}.thresholds: partial burst-latch config: {_present} set but {missing} missing"
        )
    if _present:
        if thresholds["burst_exit"] >= thresholds["burst_enter.anger"]:
            raise ValueError(
                f"{ctx}.thresholds: burst_exit ({thresholds['burst_exit']}) must be < "
                f"burst_enter.anger ({thresholds['burst_enter.anger']}) -- the hysteresis "
                "must be real or the latch thrashes"
            )
        if thresholds.get("burst_confirm_ticks", 1.0) < 1.0:
            raise ValueError(f"{ctx}.thresholds: burst_confirm_ticks must be >= 1")
    drives = dict(merged.get("drives", {}))
    action_params = dict(merged.get("action_params", {}))
    mapper_params = {
        k: float(v) for k, v in dict(merged.get("mapper_params", {})).items()
    }
    history_params = {
        k: float(v) for k, v in dict(merged.get("history_params", {})).items()
    }
    param_bounds = dict(merged.get("param_bounds", {}))
    calibration = dict(merged.get("calibration", {}))
    appraisal = dict(merged.get("appraisal", {}))

    return PersonaConfig(
        id=persona_id,
        traits=traits,
        initial_global_state=initial_global_state,
        initial_relations=initial_relations,
        affinities=affinities,
        half_lives=half_lives,
        setpoints=setpoints,
        drifts=drifts,
        decay=decay,
        dt=dt,
        gains=gains,
        couplings=couplings,
        coupling_escalation=coupling_escalation,
        burst_extinction=burst_extinction,
        gain_modulators=gain_modulators,
        idle_recovery=idle_recovery,
        idle_recovery_modulator=idle_recovery_modulator,
        idle_recovery_floor=idle_recovery_floor,
        derived_weights=derived_weights,
        potential_terms=potential_terms,
        potential_weights=potential_weights,
        filter_weights=filter_weights,
        thresholds=thresholds,
        drives=drives,
        action_params=action_params,
        mapper_params=mapper_params,
        history_params=history_params,
        param_bounds=param_bounds,
        calibration=calibration,
        appraisal=appraisal,
    )


def load_scenario(scenario_path: str | Path) -> Scenario:
    raw = _load_yaml(scenario_path)
    ctx = str(scenario_path)
    events: list[RawEvent] = []
    for i, ev in enumerate(list(raw.get("events", []))):
        ev = dict(ev)
        events.append(
            RawEvent(
                type=str(_require(ev, "type", f"{ctx}.events[{i}]")),
                t=int(_require(ev, "t", f"{ctx}.events[{i}]")),
                source=ev.get("source"),
                target=ev.get("target"),
                item=ev.get("item"),
                topic=ev.get("topic"),
                faction=ev.get("faction"),
                intensity=float(ev.get("intensity", 1.0)),
                context=dict(ev.get("context", {})),
            )
        )
    events.sort(key=lambda e: e.t)
    return Scenario(
        id=str(_require(raw, "id", ctx)),
        persona=str(_require(raw, "persona", ctx)),
        initial_overrides=dict(raw.get("initial_overrides", {})),
        events=tuple(events),
    )
