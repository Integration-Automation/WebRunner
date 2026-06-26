"""
遍歷所有頁,斷言無重複 / 無遺漏 / cursor 穩定。
Common pagination bugs:

* Off-by-one: missing 1 row at every page boundary
* Duplicate item across pages (sort key not stable under concurrent
  writes)
* Cursor changes meaning when the result set mutates
* "Empty next page" never terminates (infinite loop)

This module drives a user-supplied :class:`PageFetcher` through every
page until exhaustion (or hits ``max_pages`` safety limit) and reports
counts + violations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Protocol

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PaginationAuditError(WebRunnerException):
    """Raised on bad inputs or detected pagination issues."""


# ---------- model ------------------------------------------------------

@dataclass
class Page:
    """One fetched page."""

    items: list[Any]
    next_cursor: Any | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, list):
            raise PaginationAuditError("Page.items must be a list")


class PageFetcher(Protocol):
    """Caller-supplied fetcher."""

    def __call__(self, cursor: Any | None) -> Page: ...


KeyFn = Callable[[Any], Hashable]
"""Function: item → hashable identity (e.g. ``lambda r: r['id']``)."""


# ---------- audit ------------------------------------------------------

@dataclass
class PaginationFindings:
    """Result of :func:`walk_all_pages`."""

    page_count: int = 0
    total_items: int = 0
    unique_items: int = 0
    duplicates: list[Hashable] = field(default_factory=list)
    duplicate_pages: dict[Hashable, list[int]] = field(default_factory=dict)
    empty_pages: list[int] = field(default_factory=list)
    cursor_loop: bool = False
    hit_max_pages: bool = False
    item_keys_by_page: list[list[Hashable]] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.duplicates and not self.cursor_loop and not self.hit_max_pages


def walk_all_pages(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    fetcher: PageFetcher,
    key_fn: KeyFn,
    *,
    max_pages: int = 1_000,
    initial_cursor: Any | None = None,
) -> PaginationFindings:
    """
    Iterate pages until ``next_cursor`` is None (or ``max_pages`` reached),
    accumulating duplicates, empty-page indices, and cursor-loop detection.
    """
    if not callable(fetcher):
        raise PaginationAuditError("fetcher must be callable")
    if not callable(key_fn):
        raise PaginationAuditError("key_fn must be callable")
    if max_pages <= 0:
        raise PaginationAuditError("max_pages must be > 0")

    findings = PaginationFindings()
    seen_cursors: set = set()
    seen_items: dict[Hashable, list[int]] = {}
    cursor: Any | None = initial_cursor
    page_index = 0
    while page_index < max_pages:
        try:
            page = fetcher(cursor)
        except Exception as error:
            raise PaginationAuditError(
                f"fetcher raised at page {page_index}: {error!r}"
            ) from error
        if not isinstance(page, Page):
            raise PaginationAuditError(
                f"fetcher must return Page, got {type(page).__name__}"
            )
        findings.page_count = page_index + 1
        page_keys: list[Hashable] = []
        for item in page.items:
            try:
                key = key_fn(item)
            except Exception as error:
                raise PaginationAuditError(
                    f"key_fn failed on page {page_index}: {error!r}"
                ) from error
            seen_items.setdefault(key, []).append(page_index)
            page_keys.append(key)
        findings.total_items += len(page.items)
        findings.item_keys_by_page.append(page_keys)
        if not page.items:
            findings.empty_pages.append(page_index)
        if page.next_cursor is None:
            break
        cursor_key = _hashable_cursor(page.next_cursor)
        if cursor_key in seen_cursors:
            findings.cursor_loop = True
            break
        seen_cursors.add(cursor_key)
        cursor = page.next_cursor
        page_index += 1
    else:
        findings.hit_max_pages = True

    for key, page_list in seen_items.items():
        if len(page_list) > 1:
            findings.duplicates.append(key)
            findings.duplicate_pages[key] = page_list
    findings.unique_items = len(seen_items)
    return findings


def _hashable_cursor(cursor: Any) -> Hashable:
    if isinstance(cursor, (str, int, float, bool, type(None))):
        return cursor
    try:
        return repr(cursor)
    except Exception:
        return id(cursor)


# ---------- assertions -------------------------------------------------

def assert_no_duplicates(findings: PaginationFindings) -> None:
    """Raise if any item key appeared on more than one page."""
    if findings.duplicates:
        sample = ", ".join(repr(k) for k in findings.duplicates[:5])
        more = (
            "" if len(findings.duplicates) <= 5
            else f" (+{len(findings.duplicates) - 5})"
        )
        raise PaginationAuditError(f"duplicate items across pages: {sample}{more}")


def assert_no_cursor_loop(findings: PaginationFindings) -> None:
    """Raise if a cursor was reused (would loop forever)."""
    if findings.cursor_loop:
        raise PaginationAuditError("cursor loop detected")


def assert_terminated(findings: PaginationFindings) -> None:
    """Raise if ``max_pages`` was hit before exhaustion."""
    if findings.hit_max_pages:
        raise PaginationAuditError(
            f"pagination did not terminate within {findings.page_count} pages"
        )


def assert_expected_total(
    findings: PaginationFindings, *, expected_total: int,
) -> None:
    """Assert ``unique_items`` matches ``expected_total``."""
    if expected_total < 0:
        raise PaginationAuditError("expected_total must be >= 0")
    if findings.unique_items != expected_total:
        raise PaginationAuditError(
            f"unique items {findings.unique_items} != expected {expected_total}"
        )


def assert_clean(findings: PaginationFindings) -> None:
    """All of the above in one go."""
    if not isinstance(findings, PaginationFindings):
        raise PaginationAuditError("assert_clean expects PaginationFindings")
    assert_no_duplicates(findings)
    assert_no_cursor_loop(findings)
    assert_terminated(findings)


# ---------- ordering check --------------------------------------------

def assert_sorted_by(
    findings: PaginationFindings,
    items_by_page_key: KeyFn,
    *,
    reverse: bool = False,
) -> None:
    """
    Assert each page (and inter-page boundary) is sorted by ``items_by_page_key``.
    Different from :func:`assert_no_duplicates` — this catches "page 3
    items come BEFORE page 2 items" bugs that look fine within a page.
    """
    if not callable(items_by_page_key):
        raise PaginationAuditError("items_by_page_key must be callable")
    try:
        flattened: list[Hashable] = [
            items_by_page_key(key)
            for page_keys in findings.item_keys_by_page
            for key in page_keys
        ]
    except Exception as error:
        raise PaginationAuditError(
            f"items_by_page_key failed: {error!r}"
        ) from error
    if not flattened:
        return
    last = flattened[0]
    for current in flattened[1:]:
        if reverse:
            if current > last:
                raise PaginationAuditError(
                    f"order violation: {current!r} > {last!r} but reverse=True"
                )
        else:
            if current < last:
                raise PaginationAuditError(
                    f"order violation: {current!r} < {last!r}"
                )
        last = current
