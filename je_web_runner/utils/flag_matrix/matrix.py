"""
Feature flag 組合矩陣執行,自動剪掉冗餘 / 不可能組合。
Brute-force cartesian on N flags blows up fast (3 flags × 3 variants = 27).
This module lets you declare:

* **flags & variants** — what to permute
* **constraints** — pairs that must / must not appear together
* **pinned combos** — must-include baselines (e.g. "all off", "all on")
* **sample_size** — cap, with deterministic seeded sampling

It produces a :class:`FlagMatrix` of dict combos that downstream test
runners iterate over. There is also a tiny "result accumulator" to record
pass/fail per combo and pick the minimal failing subset for the report.
"""
from __future__ import annotations

import itertools
import json
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FlagMatrixError(WebRunnerException):
    """Raised on bad flag definitions, impossible constraints, or sample size."""


Combo = dict[str, Any]
Constraint = Callable[[Combo], bool]


# ---------- definitions -------------------------------------------------

@dataclass
class FlagSpec:
    """A single flag and the values it can take."""

    name: str
    variants: Sequence[Any]

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise FlagMatrixError(f"flag name must be a non-empty string, got {self.name!r}")
        if not self.variants:
            raise FlagMatrixError(f"flag {self.name!r} has no variants")
        if len(set(map(repr, self.variants))) != len(self.variants):
            raise FlagMatrixError(f"flag {self.name!r} has duplicate variants")


@dataclass
class FlagMatrix:
    """The materialised set of combos and metadata."""

    combos: list[Combo] = field(default_factory=list)
    total_possible: int = 0
    pinned_count: int = 0
    constrained_out: int = 0
    sampled: bool = False
    seed: int | None = None

    def __len__(self) -> int:
        return len(self.combos)

    def __iter__(self):
        return iter(self.combos)


# ---------- builders ----------------------------------------------------

def build_matrix(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    flags: Sequence[FlagSpec],
    *,
    constraints: Sequence[Constraint] = (),
    pinned: Sequence[Combo] = (),
    sample_size: int | None = None,
    seed: int | None = None,
) -> FlagMatrix:
    """
    Materialise the combo list. ``constraints`` returning False drop a
    combo. ``pinned`` always appears at the front. ``sample_size`` (if
    set) limits the total combo count via deterministic seeded sampling.
    """
    if not flags:
        raise FlagMatrixError("at least one FlagSpec is required")
    seen_names = [f.name for f in flags]
    if len(set(seen_names)) != len(seen_names):
        raise FlagMatrixError(f"duplicate flag name in: {seen_names}")
    if sample_size is not None and sample_size <= 0:
        raise FlagMatrixError("sample_size must be > 0 when provided")

    names = [f.name for f in flags]
    variant_lists = [list(f.variants) for f in flags]
    total_possible = 1
    for variants in variant_lists:
        total_possible *= len(variants)

    all_combos: list[Combo] = []
    for tup in itertools.product(*variant_lists):
        combo = dict(zip(names, tup, strict=False))
        all_combos.append(combo)

    pinned_combos: list[Combo] = []
    pinned_keys = set()
    for combo in pinned:
        _validate_pinned(combo, names, variant_lists)
        key = _combo_key(combo)
        if key in pinned_keys:
            continue
        pinned_keys.add(key)
        pinned_combos.append(combo)

    filtered: list[Combo] = []
    constrained_out = 0
    for combo in all_combos:
        if _combo_key(combo) in pinned_keys:
            continue
        if _passes_all(combo, constraints):
            filtered.append(combo)
        else:
            constrained_out += 1

    if not pinned_combos and not filtered:
        raise FlagMatrixError("all combos were filtered out by constraints")

    if sample_size is not None and len(filtered) > max(0, sample_size - len(pinned_combos)):
        rng = random.Random(seed)  # nosec B311 — deterministic flag-combo sampling, not crypto
        keep_count = max(0, sample_size - len(pinned_combos))
        # S2245 ok: deterministic seeded sampling for reproducible test combos;
        # not used for any cryptographic / security decision.
        filtered = rng.sample(filtered, keep_count)  # NOSONAR S2245 — non-crypto use (chaos/sampling), not security-sensitive
        sampled = True
    else:
        sampled = False

    combos = pinned_combos + filtered
    return FlagMatrix(
        combos=combos,
        total_possible=total_possible,
        pinned_count=len(pinned_combos),
        constrained_out=constrained_out,
        sampled=sampled,
        seed=seed,
    )


def _validate_pinned(
    combo: Combo,
    names: Sequence[str],
    variant_lists: Sequence[Sequence[Any]],
) -> None:
    if not isinstance(combo, dict):
        raise FlagMatrixError(f"pinned combo must be a dict, got {type(combo).__name__}")
    if set(combo.keys()) != set(names):
        raise FlagMatrixError(
            f"pinned combo keys {sorted(combo.keys())} != flag names {sorted(names)}"
        )
    for name, variants in zip(names, variant_lists, strict=False):
        if combo[name] not in variants:
            raise FlagMatrixError(
                f"pinned combo value {combo[name]!r} for flag {name!r} "
                f"is not in declared variants {variants!r}"
            )


def _combo_key(combo: Combo) -> str:
    return json.dumps(combo, sort_keys=True, default=str)


def _passes_all(combo: Combo, constraints: Sequence[Constraint]) -> bool:
    for constraint in constraints:
        try:
            if not constraint(combo):
                return False
        except Exception as error:
            raise FlagMatrixError(
                f"constraint raised on combo {combo}: {error!r}"
            ) from error
    return True


# ---------- constraint helpers ------------------------------------------

def forbid(pair: tuple[tuple[str, Any], tuple[str, Any]]) -> Constraint:
    """Block combos containing both ``(flag_a, val_a)`` AND ``(flag_b, val_b)``."""
    (a_flag, a_val), (b_flag, b_val) = pair

    def _constraint(combo: Combo) -> bool:
        return not (combo.get(a_flag) == a_val and combo.get(b_flag) == b_val)
    return _constraint


def require(pair: tuple[tuple[str, Any], tuple[str, Any]]) -> Constraint:
    """If ``(flag_a, val_a)`` is set, ``(flag_b, val_b)`` must also be set."""
    (a_flag, a_val), (b_flag, b_val) = pair

    def _constraint(combo: Combo) -> bool:
        if combo.get(a_flag) != a_val:
            return True
        return combo.get(b_flag) == b_val
    return _constraint


# ---------- results -----------------------------------------------------

@dataclass
class ComboResult:
    """Outcome of executing one combo."""

    combo: Combo
    passed: bool
    duration_seconds: float = 0.0
    error: str | None = None


@dataclass
class MatrixReport:
    """Roll-up of every :class:`ComboResult`."""

    total: int
    passed: int
    failed: int
    failures: list[ComboResult] = field(default_factory=list)
    average_seconds: float = 0.0


def summarise_results(results: Iterable[ComboResult]) -> MatrixReport:
    """Compute counts and pull out the failures."""
    total = 0
    passed = 0
    failures: list[ComboResult] = []
    total_seconds = 0.0
    for result in results:
        if not isinstance(result, ComboResult):
            raise FlagMatrixError(
                f"summarise_results expects ComboResult, got {type(result).__name__}"
            )
        total += 1
        total_seconds += result.duration_seconds
        if result.passed:
            passed += 1
        else:
            failures.append(result)
    avg = (total_seconds / total) if total else 0.0
    return MatrixReport(
        total=total,
        passed=passed,
        failed=total - passed,
        failures=failures,
        average_seconds=round(avg, 4),
    )


def smallest_failing_subset(failures: Sequence[ComboResult]) -> list[str]:
    """
    Pick out the smallest set of flags that, alone, explain every failure.
    Greedy minimum-set-cover on ``{flag=value}`` strings. Useful for the
    PR comment so reviewers see "all failures involve checkout=v2" rather
    than 30 individual combos.
    """
    if not failures:
        return []
    universe = set(range(len(failures)))
    sets: dict[str, set] = {}
    for index, failure in enumerate(failures):
        for flag, value in failure.combo.items():
            sets.setdefault(f"{flag}={value!r}", set()).add(index)
    chosen: list[str] = []
    covered: set = set()
    while covered != universe:
        best_key = None
        best_gain = -1
        for key, indices in sets.items():
            gain = len(indices - covered)
            if gain > best_gain:
                best_gain = gain
                best_key = key
        if best_key is None or best_gain <= 0:
            break
        chosen.append(best_key)
        covered |= sets[best_key]
    return chosen
