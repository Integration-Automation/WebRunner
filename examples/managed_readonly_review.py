"""Host-only review of an already owned page; importing this example starts nothing.

Call on the owner's thread after its last operation has returned. The selector and
expected value belong to a reviewed independent completion condition. This example
does not establish server state, task authority or AutoControl helper ownership.
"""
from je_web_runner import ManagedBrowserSession


def review_retained_text(owner: ManagedBrowserSession, selector: str, expected: str) -> bool:
    """Permanently retire input/network, compare fresh DOM text, then close this owner."""
    with owner.freeze_readonly() as review:
        return review.text(selector) == expected
