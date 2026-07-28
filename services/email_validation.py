"""Signup-time email checks for the free 3-caption sample.

These guards exist to catch typos and obviously dead domains — not to police users.
The dominant real-world failure is someone typing "gmial.com", never receiving their
captions, and silently disappearing. That costs a lead we already paid for.

Two rules follow from that:

1. **Fail open.** A DNS hiccup, a missing resolver library, a slow lookup — none of
   these may cost a signup. Anything we cannot answer confidently is allowed through.
2. **Never a dead end.** A rejection always carries either a suggestion or a way to
   proceed anyway (see ``validate_signup_email``'s ``allow_override``), so a genuine
   address on an unusual domain is never permanently blocked.
"""

from __future__ import annotations

from typing import Optional, Tuple

# Deliberately loose: full RFC 5322 validation rejects addresses that work fine in
# practice. We only rule out what cannot be an address at all.
_MIN_PARTS = 2

# Domains a mistyped address most often *meant*. Ordered by how common they are for
# UK/US small businesses, which is who this product sells to.
COMMON_DOMAINS = (
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "hotmail.co.uk",
    "yahoo.com",
    "yahoo.co.uk",
    "icloud.com",
    "me.com",
    "live.com",
    "live.co.uk",
    "msn.com",
    "aol.com",
    "btinternet.com",
    "sky.com",
    "virginmedia.com",
    "protonmail.com",
    "proton.me",
)

# Max edit distance at which we will suggest a correction. 2 catches "gmial.com" and
# "gmai.com" without flagging genuinely different short domains.
_MAX_SUGGEST_DISTANCE = 2

_DNS_TIMEOUT_SECONDS = 2.0


def normalize_email(email: Optional[str]) -> str:
    """Trim and lowercase. Nothing more — see module docstring on failing open."""
    return (email or "").strip().lower()


def split_email(email: str) -> Tuple[str, str]:
    """Return (local, domain). Both empty when the address has no usable @ split."""
    normalized = normalize_email(email)
    if normalized.count("@") != 1:
        return "", ""
    local, _, domain = normalized.partition("@")
    return local.strip(), domain.strip()


def is_plausible_address(email: str) -> bool:
    """True when the string could be an email address at all.

    Intentionally permissive: exactly one @, something either side, and a dotted
    domain with a non-numeric final label.
    """
    local, domain = split_email(email)
    if not local or not domain:
        return False
    if " " in local or " " in domain:
        return False
    labels = domain.split(".")
    if len(labels) < _MIN_PARTS or not all(labels):
        return False
    tld = labels[-1]
    return len(tld) >= 2 and not tld.isdigit()


def _levenshtein(a: str, b: str) -> int:
    """Edit distance, iterative two-row form (no dependency, adequate for domains)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,          # deletion
                    current[j - 1] + 1,       # insertion
                    previous[j - 1] + (ca != cb),  # substitution
                )
            )
        previous = current
    return previous[-1]


def suggest_domain_correction(email: str) -> Optional[str]:
    """Suggest a corrected full address, or None.

    Returns None when the domain is already a known-good one, so we never nag a
    correct address.
    """
    local, domain = split_email(email)
    if not local or not domain or domain in COMMON_DOMAINS:
        return None

    best: Optional[str] = None
    best_distance = _MAX_SUGGEST_DISTANCE + 1
    for candidate in COMMON_DOMAINS:
        # Guard against short domains matching everything within distance 2.
        if abs(len(candidate) - len(domain)) > _MAX_SUGGEST_DISTANCE:
            continue
        distance = _levenshtein(domain, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance

    if best is None or best_distance > _MAX_SUGGEST_DISTANCE:
        return None
    return f"{local}@{best}"


def domain_accepts_mail(domain: str) -> Optional[bool]:
    """True / False / None, where None means 'could not determine — allow it'.

    Uses dnspython when installed. Without it we return None rather than falling back
    to an A-record probe: a blocking getaddrinfo has no per-call timeout and could hang
    the signup request, which is a worse failure than skipping the check.
    """
    domain = (domain or "").strip().lower()
    if not domain:
        return None
    try:
        import dns.resolver  # type: ignore
    except ImportError:
        return None

    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = _DNS_TIMEOUT_SECONDS
        resolver.lifetime = _DNS_TIMEOUT_SECONDS
        answers = resolver.resolve(domain, "MX")
        return bool(len(answers))
    except Exception as exc:  # noqa: BLE001 - see below
        name = type(exc).__name__
        # Only these two mean "this domain definitively cannot receive mail".
        # Timeouts, no-nameserver, and anything else are inconclusive -> allow.
        if name in ("NXDOMAIN", "NoAnswer"):
            return False
        return None


def validate_signup_email(
    email: str, *, allow_override: bool = False
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check an address at sample signup.

    Returns ``(ok, error, suggestion)``. ``suggestion`` may be present alongside a
    successful result, so the caller can offer a gentle "did you mean…" without
    blocking.

    ``allow_override=True`` skips the deliverability check, for the second attempt
    after a user has confirmed the address they typed really is correct.
    """
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 254 or not is_plausible_address(normalized):
        return False, "Please enter a valid email address.", None

    suggestion = suggest_domain_correction(normalized)
    if allow_override:
        return True, None, suggestion

    _, domain = split_email(normalized)
    if domain_accepts_mail(domain) is False:
        if suggestion:
            return False, f"We couldn't find a mail server for “{domain}”.", suggestion
        return False, f"We couldn't find a mail server for “{domain}”.", None

    return True, None, suggestion
