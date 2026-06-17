"""Security guards for content and network transport.

- Hidden Unicode scanning: zero-width characters, bidi formatting controls,
  and tag characters are common vectors for invisible prompt injection.
- Insecure transport blocking: plain http:// is rejected unless explicitly
  allowed.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


class HiddenUnicodeError(ValueError):
    """Raised when hidden/invisible Unicode characters are found."""


class InsecureTransportError(ValueError):
    """Raised when a plain http:// transport is used without opt-in."""


# Unicode code points treated as hidden/invisible.
_HIDDEN_RANGES: tuple[tuple[int, int], ...] = (
    # Zero-width / invisible formatting characters
    (0x200B, 0x200F),  # ZWSP, ZWNJ, ZWJ, LRM, RLM
    (0x2060, 0x2060),  # word joiner
    (0x180E, 0x180E),  # Mongolian vowel separator
    # Bidirectional formatting controls
    (0x202A, 0x202E),  # LRE, RLE, PDF, LRO, RLO
    (0x2066, 0x2069),  # LRI, RLI, FSI, PDI
    # Tag characters (rendered invisibly by most software)
    (0xE0000, 0xE007F),
)

# Surrogate code points should never appear in valid Unicode text; the
# U+DB40 block is sometimes used to smuggle tag-like characters.
_SURROGATE_RANGE = (0xD800, 0xDFFF)

# Byte order mark is also a zero-width character and a common stowaway.
_BOM = 0xFEFF


def _is_hidden(codepoint: int) -> bool:
    if codepoint == _BOM:
        return True
    if _SURROGATE_RANGE[0] <= codepoint <= _SURROGATE_RANGE[1]:
        return True
    for start, end in _HIDDEN_RANGES:
        if start <= codepoint <= end:
            return True
    return False


def _char_description(codepoint: int) -> str:
    name = {
        0x200B: "ZWSP",
        0x200C: "ZWNJ",
        0x200D: "ZWJ",
        0x200E: "LRM",
        0x200F: "RLM",
        0x202A: "LRE",
        0x202B: "RLE",
        0x202C: "PDF",
        0x202D: "LRO",
        0x202E: "RLO",
        0x2060: "WJ",
        0x2066: "LRI",
        0x2067: "RLI",
        0x2068: "FSI",
        0x2069: "PDI",
        0x180E: "MVS",
        0xFEFF: "BOM/ZWNBSP",
    }.get(codepoint)
    if name:
        return f"U+{codepoint:04X} ({name})"
    return f"U+{codepoint:04X}"


def _find_hidden(text: str, source: str | None = None) -> list[str]:
    findings: list[str] = []
    line = 1
    col = 1
    prefix = f"{source}: " if source else ""
    for char in text:
        codepoint = ord(char)
        if _is_hidden(codepoint):
            findings.append(
                f"{prefix}hidden character {_char_description(codepoint)} at line {line}, column {col}"
            )
        if char == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return findings


def scan_text(text: str, *, source: str | None = None) -> list[str]:
    """Return a list of human-readable hidden-Unicode findings in `text`."""
    return _find_hidden(text, source)


def scan_file(path: Path, *, source: str | None = None) -> list[str]:
    """Scan a single UTF-8 file for hidden Unicode characters."""
    label = source or str(path)
    text = path.read_text(encoding="utf-8")
    return _find_hidden(text, label)


def scan_directory(root: Path, *, pattern: str = "**/*") -> list[str]:
    """Scan every UTF-8 file under `root` matching `pattern`.

    Files that are not valid UTF-8 are skipped rather than treated as attacks.
    """
    findings: list[str] = []
    for path in root.glob(pattern):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(_find_hidden(text, str(path)))
    return findings


def assert_no_hidden_unicode(text: str, *, source: str | None = None) -> None:
    """Raise `HiddenUnicodeError` if hidden Unicode characters are found."""
    findings = _find_hidden(text, source)
    if findings:
        raise HiddenUnicodeError("; ".join(findings))


def require_secure_url(url: str, *, allow_insecure: bool = False) -> None:
    """Reject plain http:// URLs unless `allow_insecure` is True.

    Allows https://, file://, ssh://, git@host:path, and any other non-HTTP
    scheme.
    """
    scheme = urlparse(url).scheme.lower()
    if scheme == "http" and not allow_insecure:
        raise InsecureTransportError(
            f"insecure transport {url!r}: plain http:// is blocked; use https:// or pass --allow-insecure"
        )
