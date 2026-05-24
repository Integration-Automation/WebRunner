"""
Mutation testing for action JSON：對 action 套用變異後執行，反向驗證測試本身的偵測能力。

Mutation testing of WebRunner action JSON files. Given a passing test, we
apply a catalogue of mutations (locator swap, timeout shrink, URL change,
assertion flip, action removal, adjacent reorder) and re-run. A mutation
is "killed" when the mutated test fails. The mutation score is
``killed / total`` — high scores mean the test is sensitive, low scores
mean the test passes regardless of obvious sabotage.

The executor is caller-supplied (``Callable[[List[Any]], bool]``) so the
module stays decoupled from the Selenium/Playwright runtime and is easy
to test offline.
"""
from __future__ import annotations

import copy
import json
import random
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class MutationTestingError(WebRunnerException):
    """Raised on invalid input or executor protocol violations."""


class MutationType(str, Enum):
    LOCATOR_SWAP = "locator_swap"
    TIMEOUT_SHRINK = "timeout_shrink"
    URL_CHANGE = "url_change"
    ASSERTION_FLIP = "assertion_flip"
    ACTION_REMOVAL = "action_removal"
    ADJACENT_REORDER = "adjacent_reorder"


_DEFAULT_MUTATION_TYPES: Sequence[MutationType] = tuple(MutationType)

_LOCATOR_KEYS = ("test_object_name", "value", "locator", "selector")
_URL_KEYS = ("url", "target_url", "expected_url")
_TIMEOUT_KEYS = ("timeout", "wait_seconds", "delay")
_ASSERTION_KEYS = ("expected", "expected_value", "expected_text")
_NON_REMOVABLE_PREFIXES = ("WR_set_", "WR_quit", "WR_init", "WR_to_url")


@dataclass
class Mutation:
    """One mutation applied to a copy of the action list."""

    type: MutationType
    action_index: int
    description: str
    original: Any = None
    mutated: Any = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["type"] = self.type.value
        return out


@dataclass
class MutationResult:
    """Outcome of running one mutation through the executor."""

    mutation: Mutation
    killed: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation": self.mutation.to_dict(),
            "killed": self.killed,
            "error": self.error,
        }


@dataclass
class MutationScore:
    """Aggregate mutation score for a single action file."""

    total: int
    killed: int
    survived: int
    score: float
    results: List[MutationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "killed": self.killed,
            "survived": self.survived,
            "score": self.score,
            "results": [r.to_dict() for r in self.results],
        }


# ---------- helpers ------------------------------------------------------

def _kwargs_of(action: List[Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(action, list) or not action:
        return None
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2]
    if len(action) >= 2 and isinstance(action[1], dict):
        return action[1]
    return None


def _action_command(action: List[Any]) -> str:
    if isinstance(action, list) and action and isinstance(action[0], str):
        return action[0]
    return ""


# ---------- mutation generators -----------------------------------------

def _gen_locator_swap(actions: List[Any]) -> List[Mutation]:
    mutations: List[Mutation] = []
    for idx, action in enumerate(actions):
        kwargs = _kwargs_of(action)
        if not kwargs:
            continue
        for key in _LOCATOR_KEYS:
            if key in kwargs and isinstance(kwargs[key], str):
                mutations.append(Mutation(
                    type=MutationType.LOCATOR_SWAP,
                    action_index=idx,
                    description=f"swap {key} → '__mutated_{key}__'",
                    original=kwargs[key],
                    mutated=f"__mutated_{key}__",
                ))
                break
    return mutations


def _gen_timeout_shrink(actions: List[Any]) -> List[Mutation]:
    mutations: List[Mutation] = []
    for idx, action in enumerate(actions):
        kwargs = _kwargs_of(action)
        if not kwargs:
            continue
        for key in _TIMEOUT_KEYS:
            if key in kwargs and isinstance(kwargs[key], (int, float)):
                mutations.append(Mutation(
                    type=MutationType.TIMEOUT_SHRINK,
                    action_index=idx,
                    description=f"shrink {key} → 0.001",
                    original=kwargs[key],
                    mutated=0.001,
                ))
                break
    return mutations


def _gen_url_change(actions: List[Any]) -> List[Mutation]:
    mutations: List[Mutation] = []
    for idx, action in enumerate(actions):
        kwargs = _kwargs_of(action)
        if not kwargs:
            continue
        for key in _URL_KEYS:
            if key in kwargs and isinstance(kwargs[key], str):
                mutations.append(Mutation(
                    type=MutationType.URL_CHANGE,
                    action_index=idx,
                    description=f"swap {key} → 'https://example.invalid/mut'",
                    original=kwargs[key],
                    mutated="https://example.invalid/mut",
                ))
                break
    return mutations


def _flip_assertion_value(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return value + "__MUTATED__"
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, list):
        return list(reversed(value))
    return f"__MUTATED__{value!r}"


def _gen_assertion_flip(actions: List[Any]) -> List[Mutation]:
    mutations: List[Mutation] = []
    for idx, action in enumerate(actions):
        kwargs = _kwargs_of(action)
        if not kwargs:
            continue
        for key in _ASSERTION_KEYS:
            if key in kwargs:
                flipped = _flip_assertion_value(kwargs[key])
                mutations.append(Mutation(
                    type=MutationType.ASSERTION_FLIP,
                    action_index=idx,
                    description=f"flip {key}",
                    original=kwargs[key],
                    mutated=flipped,
                ))
                break
    return mutations


def _gen_action_removal(actions: List[Any]) -> List[Mutation]:
    mutations: List[Mutation] = []
    for idx, action in enumerate(actions):
        command = _action_command(action)
        if not command:
            continue
        if any(command.startswith(prefix) for prefix in _NON_REMOVABLE_PREFIXES):
            continue
        mutations.append(Mutation(
            type=MutationType.ACTION_REMOVAL,
            action_index=idx,
            description=f"remove {command}",
            original=action,
            mutated=None,
        ))
    return mutations


def _gen_adjacent_reorder(actions: List[Any]) -> List[Mutation]:
    mutations: List[Mutation] = []
    for idx in range(len(actions) - 1):
        if not isinstance(actions[idx], list) or not isinstance(actions[idx + 1], list):
            continue
        if not actions[idx] or not actions[idx + 1]:
            continue
        cmd_a = _action_command(actions[idx])
        cmd_b = _action_command(actions[idx + 1])
        if any(cmd_a.startswith(p) for p in _NON_REMOVABLE_PREFIXES):
            continue
        if any(cmd_b.startswith(p) for p in _NON_REMOVABLE_PREFIXES):
            continue
        mutations.append(Mutation(
            type=MutationType.ADJACENT_REORDER,
            action_index=idx,
            description=f"swap actions {idx} and {idx + 1}",
            original=(cmd_a, cmd_b),
            mutated=(cmd_b, cmd_a),
        ))
    return mutations


_GENERATORS: Dict[MutationType, Callable[[List[Any]], List[Mutation]]] = {
    MutationType.LOCATOR_SWAP: _gen_locator_swap,
    MutationType.TIMEOUT_SHRINK: _gen_timeout_shrink,
    MutationType.URL_CHANGE: _gen_url_change,
    MutationType.ASSERTION_FLIP: _gen_assertion_flip,
    MutationType.ACTION_REMOVAL: _gen_action_removal,
    MutationType.ADJACENT_REORDER: _gen_adjacent_reorder,
}


def generate_mutations(
    actions: List[Any],
    types: Sequence[MutationType] = _DEFAULT_MUTATION_TYPES,
    *,
    seed: Optional[int] = None,
    max_per_type: Optional[int] = None,
) -> List[Mutation]:
    """
    依 mutation type 對 action list 生出可能的變異。
    Run every configured generator and concatenate. ``max_per_type`` caps
    each type's contribution (deterministic when ``seed`` is set) so very
    large suites don't generate hundreds of mutations.
    """
    if not isinstance(actions, list):
        raise MutationTestingError(f"actions must be a list, got {type(actions).__name__}")
    rng = random.Random(seed) if seed is not None else random
    all_mutations: List[Mutation] = []
    for mt in types:
        generator = _GENERATORS.get(mt)
        if generator is None:
            continue
        generated = generator(actions)
        if max_per_type is not None and len(generated) > max_per_type:
            generated = rng.sample(generated, max_per_type)
        all_mutations.extend(generated)
    return all_mutations


# ---------- apply ---------------------------------------------------------

def apply_mutation(actions: List[Any], mutation: Mutation) -> List[Any]:
    """
    產生一份套了 mutation 的 actions（不修改原 list）。
    Return a deep-copied action list with ``mutation`` applied. Mutations
    targeting an out-of-range index raise :class:`MutationTestingError`
    so the executor never receives a malformed list.
    """
    if mutation.action_index < 0 or mutation.action_index >= len(actions):
        raise MutationTestingError(
            f"mutation index {mutation.action_index} out of range for {len(actions)} actions"
        )
    new_actions = copy.deepcopy(actions)
    if mutation.type is MutationType.ACTION_REMOVAL:
        del new_actions[mutation.action_index]
        return new_actions
    if mutation.type is MutationType.ADJACENT_REORDER:
        idx = mutation.action_index
        if idx + 1 >= len(new_actions):
            raise MutationTestingError("reorder requires a following action")
        new_actions[idx], new_actions[idx + 1] = new_actions[idx + 1], new_actions[idx]
        return new_actions
    kwargs = _kwargs_of(new_actions[mutation.action_index])
    if kwargs is None:
        raise MutationTestingError(
            f"action at index {mutation.action_index} has no kwargs to mutate"
        )
    if mutation.type is MutationType.LOCATOR_SWAP:
        for key in _LOCATOR_KEYS:
            if key in kwargs:
                kwargs[key] = mutation.mutated
                return new_actions
    if mutation.type is MutationType.TIMEOUT_SHRINK:
        for key in _TIMEOUT_KEYS:
            if key in kwargs:
                kwargs[key] = mutation.mutated
                return new_actions
    if mutation.type is MutationType.URL_CHANGE:
        for key in _URL_KEYS:
            if key in kwargs:
                kwargs[key] = mutation.mutated
                return new_actions
    if mutation.type is MutationType.ASSERTION_FLIP:
        for key in _ASSERTION_KEYS:
            if key in kwargs:
                kwargs[key] = mutation.mutated
                return new_actions
    raise MutationTestingError(
        f"could not apply mutation {mutation.type.value} at {mutation.action_index}"
    )


# ---------- runner -------------------------------------------------------

ExecutorFn = Callable[[List[Any]], bool]


def run_mutation_testing(
    actions: List[Any],
    executor: ExecutorFn,
    *,
    types: Sequence[MutationType] = _DEFAULT_MUTATION_TYPES,
    seed: Optional[int] = None,
    max_per_type: Optional[int] = None,
    stop_on_first_survivor: bool = False,
) -> MutationScore:
    """
    對每個 mutation 跑一次 executor，計算 kill rate。
    ``executor(mutated_actions)`` must return ``True`` if the mutated
    suite still passed (mutation survived) or ``False`` if the run failed
    (mutation was killed — the desired outcome). Exceptions raised by the
    executor are caught and treated as kills (failures).
    """
    mutations = generate_mutations(actions, types, seed=seed, max_per_type=max_per_type)
    results: List[MutationResult] = []
    for mutation in mutations:
        mutated = apply_mutation(actions, mutation)
        try:
            passed = bool(executor(mutated))
        except Exception as error:  # noqa: BLE001 — executor may raise
            results.append(MutationResult(
                mutation=mutation, killed=True, error=repr(error),
            ))
            continue
        results.append(MutationResult(mutation=mutation, killed=not passed))
        if stop_on_first_survivor and passed:
            web_runner_logger.info(
                f"mutation survived early: {mutation.type.value} at {mutation.action_index}"
            )
            break
    killed = sum(1 for r in results if r.killed)
    survived = sum(1 for r in results if not r.killed)
    score = (killed / len(results)) if results else 0.0
    return MutationScore(
        total=len(results),
        killed=killed,
        survived=survived,
        score=round(score, 4),
        results=results,
    )


def run_mutation_testing_on_file(
    action_path: Union[str, Path],
    executor: ExecutorFn,
    **kwargs: Any,
) -> MutationScore:
    """Convenience: load an action JSON file then run mutation testing."""
    path = Path(action_path)
    if not path.is_file():
        raise MutationTestingError(f"action file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fp:
            actions = json.load(fp)
    except (OSError, ValueError) as error:
        raise MutationTestingError(f"cannot parse {path}: {error!r}") from error
    if not isinstance(actions, list):
        raise MutationTestingError(f"top-level JSON must be a list: {path}")
    return run_mutation_testing(actions, executor, **kwargs)


# ---------- rendering ----------------------------------------------------

def render_mutation_markdown(score: MutationScore) -> str:
    """Render a mutation score as markdown for PR comments."""
    pieces = [
        "## Mutation testing report",
        "",
        f"- **Mutation score:** {score.score:.0%}",
        f"- **Total mutations:** {score.total}",
        f"- **Killed:** {score.killed}",
        f"- **Survived:** {score.survived}",
        "",
    ]
    survivors = [r for r in score.results if not r.killed]
    if survivors:
        pieces.append("### Surviving mutations (the test couldn't detect these)")
        pieces.append("| Type | Index | Description |")
        pieces.append("|------|-------|-------------|")
        for r in survivors:
            pieces.append(
                f"| `{r.mutation.type.value}` | {r.mutation.action_index} | "
                f"{r.mutation.description} |"
            )
        pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"


def assert_min_score(score: MutationScore, minimum: float = 0.8) -> None:
    """Raise ``MutationTestingError`` when ``score.score`` is below ``minimum``."""
    if score.score < minimum:
        raise MutationTestingError(
            f"mutation score {score.score:.2f} below minimum {minimum:.2f} "
            f"({score.survived} survivors)"
        )
