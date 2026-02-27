"""Filename pattern detection and proposal generation."""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FolderPattern:
    prefix: str = ""
    separator: str = "_"
    date_format: str = "YYYY-MM-DD"
    examples: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

# Date regexes: (pattern, group-name-1, group-name-2, group-name-3)
DATE_PATTERNS = [
    (r"(\d{2})\.(\d{2})\.(\d{4})", "day", "month", "year"),
    (r"(\d{4})-(\d{2})-(\d{2})", "year", "month", "day"),
    (r"(\d{2})/(\d{2})/(\d{4})", "day", "month", "year"),
    (r"(\d{4})_(\d{2})_(\d{2})", "year", "month", "day"),
    (r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", "year", "month", "day"),
]

# Context keywords that signal a document date nearby
_DATE_CONTEXT = re.compile(
    r"(?:Datum|Date|Rechnungsdatum|Invoice\s*Date|Ausstellungsdatum|"
    r"Belegdatum|vom|Erstellt\s*am|Issued)[:\s]*$",
    re.IGNORECASE,
)


_MONTH_NAMES = {
    # German
    "januar": "01", "februar": "02", "märz": "03", "maerz": "03",
    "april": "04", "mai": "05", "juni": "06", "juli": "07",
    "august": "08", "september": "09", "oktober": "10",
    "november": "11", "dezember": "12",
    # English
    "january": "01", "february": "02", "march": "03",
    "may": "05", "june": "06", "july": "07",
    "october": "10", "december": "12",
    # Abbreviations
    "jan": "01", "feb": "02", "mär": "03", "mar": "03",
    "apr": "04", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "okt": "10", "oct": "10", "nov": "11",
    "dez": "12", "dec": "12",
}

# "15. März 2024" / "November 2024" / "March 15, 2024"
_MONTH_NAME_PATTERN = re.compile(
    r"(?:(\d{1,2})\.?\s+)?"  # optional day
    r"(" + "|".join(re.escape(m) for m in sorted(_MONTH_NAMES, key=len, reverse=True)) + r")"
    r"\.?\s+(\d{4})"  # year
    r"(?!\d)",
    re.IGNORECASE,
)


def _validate_date(y: int, m: int, d: int) -> bool:
    return 1990 <= y <= 2099 and 1 <= m <= 12 and 1 <= d <= 31


def _extract_date(text: str) -> Optional[tuple[str, str, str]]:
    """Extract the most likely document date.

    Prefers dates near context keywords (Datum, Date, vom, …).
    Also handles month names (German and English).
    Falls back to the first valid date found.
    """
    # Collect all date matches with positions
    candidates: list[tuple[int, str, str, str]] = []

    # Numeric date patterns
    for pattern, *order in DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            parts = {}
            for i, name in enumerate(order):
                parts[name] = m.group(i + 1)
            y, mo, d = parts["year"], parts["month"], parts["day"]
            try:
                if _validate_date(int(y), int(mo), int(d)):
                    candidates.append((m.start(), y, mo, d))
            except ValueError:
                continue

    # Month-name patterns: "15. März 2024", "November 2024", etc.
    for m in _MONTH_NAME_PATTERN.finditer(text):
        day_str = m.group(1)
        month_name = m.group(2).lower()
        year_str = m.group(3)
        mo = _MONTH_NAMES.get(month_name)
        if mo:
            # Use empty string for day when not specified (month-only date)
            d = day_str.zfill(2) if day_str else ""
            d_val = int(d) if d else 1
            try:
                if _validate_date(int(year_str), int(mo), d_val):
                    candidates.append((m.start(), year_str, mo, d))
            except ValueError:
                continue

    if not candidates:
        return None

    # Prefer a date that has a context keyword just before it
    for pos, y, mo, d in candidates:
        before = text[max(0, pos - 40):pos]
        if _DATE_CONTEXT.search(before):
            return (y, mo, d)

    # Fall back to first date
    return (candidates[0][1], candidates[0][2], candidates[0][3])


# ---------------------------------------------------------------------------
# Sender / company extraction
# ---------------------------------------------------------------------------

# Legal suffixes that definitively mark a company name
_LEGAL_SUFFIX = re.compile(
    r"((?:[A-ZÄÖÜ][\w\-\.&]+(?:\s+|[-&]\s*))*[A-ZÄÖÜ][\w\-\.&]+)"
    r"\s+(?:GmbH|mbH|AG|Inc\.?|Ltd\.?|SE|e\.V\.|UG|KG|OHG|Co\.\s*KG|Co\.|& Co|S\.?A\.?|S\.?L\.?|plc|LLC|BV|AB)",
    re.MULTILINE,
)

# Broader sender detection from letterhead (first ~600 chars).
# Heuristic: lines that are short (company names), capitalized, and not boilerplate.
_BOILERPLATE = re.compile(
    r"(?:seite|page|tel(?:efon)?|fax|e-?mail|www\.|http|iban|bic|ust|steuer|"
    r"amtsgericht|handelsregister|geschäftsführ|bankverbindung|^\d+$|"
    r"postfach|postleitzahl|plz|^\s*$)",
    re.IGNORECASE,
)


def _extract_sender(text: str) -> str:
    """Extract sender/company name.

    Strategy:
    1. Look for a legal suffix (GmbH, AG, …) anywhere in the text.
    2. If not found, scan the letterhead (first ~600 chars) for prominent
       short lines that look like a company or person name.
    """
    # Strategy 1: legal suffix
    m = _LEGAL_SUFFIX.search(text)
    if m:
        name = m.group(1).strip()
        if "\n" in name:
            name = name.split("\n")[-1].strip()
        name = name.lstrip(".,;:- ")
        if 2 <= len(name) <= 60:
            return name

    # Strategy 2: letterhead heuristic — scan first lines
    head = text[:600]
    lines = [ln.strip() for ln in head.split("\n")]
    for line in lines:
        if not line or len(line) < 3 or len(line) > 60:
            continue
        if _BOILERPLATE.search(line):
            continue
        # Skip lines that are mostly digits/punctuation
        alpha_ratio = sum(c.isalpha() for c in line) / len(line)
        if alpha_ratio < 0.5:
            continue
        # Skip lines that look like addresses (start with digits)
        if re.match(r"^\d", line):
            continue
        # Good candidate if it has at least one uppercase word
        words = line.split()
        if any(w[0].isupper() for w in words if w and w[0].isalpha()):
            return line

    return ""


# ---------------------------------------------------------------------------
# Reference number extraction
# ---------------------------------------------------------------------------

_REF_PATTERNS = [
    # Labels that explicitly end with a number-indicator (Nr, nummer, No, #, Number)
    re.compile(
        r"(?:Rechnungs?(?:nummer|[\-\s]?[Nn]r\.?)|Beleg(?:nummer|[\-\s]?[Nn]r\.?)|"
        r"Policen?(?:nummer|[\-\s]?[Nn]r\.?)|Kunden[\-\s]?(?:Nr\.?|nummer)|"
        r"Vertrags?[\-\s]?(?:Nr\.?|nummer)|Vorgangs[\-\s]?(?:Nr\.?|nummer)|"
        r"Auftrags[\-\s]?(?:Nr\.?|nummer)|Buchungs[\-\s]?(?:Nr\.?|nummer)|"
        r"Invoice\s*(?:No\.?|Number|#)|Order\s*(?:No\.?|#)|"
        r"Ref(?:erence)?\.?\s*(?:No\.?|#)|Aktenzeichen)"
        r"[:\s.#\-]*([A-Z0-9][\w\-/.]{1,25})",
        re.IGNORECASE,
    ),
    # Bare "Nr." / "No." followed by an alphanumeric value
    re.compile(
        r"(?:Nr\.|No\.)\s*([A-Z0-9][\w\-/.]{2,25})",
        re.IGNORECASE,
    ),
]


def _extract_reference(text: str) -> str:
    """Extract invoice/reference/policy number."""
    for pat in _REF_PATTERNS:
        m = pat.search(text)
        if m:
            ref = m.group(1).strip().rstrip(".")
            # Reject if it's just a single digit or too short
            if len(ref) >= 2:
                return ref
    return ""


# ---------------------------------------------------------------------------
# Document type extraction
# ---------------------------------------------------------------------------

# (regex, label) pairs — checked in order, first match wins
_DOC_TYPE_PATTERNS = [
    (re.compile(r"\bGehaltsabrechnung\b", re.IGNORECASE), "Gehaltsabrechnung"),
    (re.compile(r"\bLohn(?:abrechnung|zettel)\b", re.IGNORECASE), "Lohnabrechnung"),
    (re.compile(r"\bEntgeltabrechnung\b", re.IGNORECASE), "Entgeltabrechnung"),
    (re.compile(r"\bKontoauszug\b", re.IGNORECASE), "Kontoauszug"),
    (re.compile(r"\bBank\s?Statement\b", re.IGNORECASE), "Bank-Statement"),
    (re.compile(r"\bGutschrift\b", re.IGNORECASE), "Gutschrift"),
    (re.compile(r"\bCredit\s?Note\b", re.IGNORECASE), "Credit-Note"),
    (re.compile(r"\bMahnung\b", re.IGNORECASE), "Mahnung"),
    (re.compile(r"\bZahlungserinnerung\b", re.IGNORECASE), "Zahlungserinnerung"),
    (re.compile(r"\bRechnung\b", re.IGNORECASE), "Rechnung"),
    (re.compile(r"\bInvoice\b", re.IGNORECASE), "Invoice"),
    (re.compile(r"\bQuittung\b", re.IGNORECASE), "Quittung"),
    (re.compile(r"\bReceipt\b", re.IGNORECASE), "Receipt"),
    (re.compile(r"\bKündigung\b", re.IGNORECASE), "Kuendigung"),
    (re.compile(r"\bTermination\b", re.IGNORECASE), "Termination"),
    (re.compile(r"\bVertrag\b", re.IGNORECASE), "Vertrag"),
    (re.compile(r"\bContract\b", re.IGNORECASE), "Contract"),
    (re.compile(r"\bAngebot\b", re.IGNORECASE), "Angebot"),
    (re.compile(r"\bQuotation\b", re.IGNORECASE), "Quotation"),
    (re.compile(r"\bBescheid\b", re.IGNORECASE), "Bescheid"),
    (re.compile(r"\bSteuerbescheid\b", re.IGNORECASE), "Steuerbescheid"),
    (re.compile(r"\bMitteilung\b", re.IGNORECASE), "Mitteilung"),
    (re.compile(r"\bBenachrichtigung\b", re.IGNORECASE), "Benachrichtigung"),
    (re.compile(r"\bVersicherungsschein\b", re.IGNORECASE), "Versicherungsschein"),
    (re.compile(r"\bPolice\b", re.IGNORECASE), "Versicherungspolice"),
    (re.compile(r"\bInsurance\b", re.IGNORECASE), "Insurance"),
    (re.compile(r"\bBestätigung\b", re.IGNORECASE), "Bestaetigung"),
    (re.compile(r"\bConfirmation\b", re.IGNORECASE), "Confirmation"),
    (re.compile(r"\bMeldebescheinigung\b", re.IGNORECASE), "Meldebescheinigung"),
    (re.compile(r"\bBescheinigung\b", re.IGNORECASE), "Bescheinigung"),
    (re.compile(r"\bAttest\b", re.IGNORECASE), "Attest"),
    (re.compile(r"\bGutachten\b", re.IGNORECASE), "Gutachten"),
    (re.compile(r"\bProtokoll\b", re.IGNORECASE), "Protokoll"),
    (re.compile(r"\bAntrag\b", re.IGNORECASE), "Antrag"),
    (re.compile(r"\bVollmacht\b", re.IGNORECASE), "Vollmacht"),
]


def _extract_doc_type(text: str) -> str:
    """Extract the document type keyword from text."""
    for pattern, label in _DOC_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return ""


# ---------------------------------------------------------------------------
# Amount extraction (for context in filename)
# ---------------------------------------------------------------------------

_AMOUNT_PATTERN = re.compile(
    r"(?:Gesamt|Total|Summe|Betrag|Endbetrag|Amount|Brutto|Netto|Zahlbetrag)"
    r"[:\s]*[€$]?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*(?:€|EUR|USD)?",
    re.IGNORECASE,
)


def _extract_amount(text: str) -> str:
    """Extract a monetary total from the document."""
    m = _AMOUNT_PATTERN.search(text)
    if m:
        amount = m.group(1).strip()
        # Normalize: 1.234,56 -> 1234.56 for filename
        if "," in amount and "." in amount:
            amount = amount.replace(".", "").replace(",", ".")
        elif "," in amount:
            amount = amount.replace(",", ".")
        return amount
    return ""


# ---------------------------------------------------------------------------
# Filename sanitization helper
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(text: str, sep: str = "_") -> str:
    """Make a string safe for use in filenames."""
    text = _UNSAFE_CHARS.sub("", text)
    text = re.sub(r'\s+', sep, text.strip())
    # Collapse repeated separators
    text = re.sub(re.escape(sep) + r'+', sep, text)
    return text.strip(sep)


# ---------------------------------------------------------------------------
# Folder pattern detection (for existing folders)
# ---------------------------------------------------------------------------

def detect_patterns(filenames: list[str]) -> FolderPattern:
    """Analyze a list of filenames to detect naming patterns."""
    if not filenames:
        return FolderPattern()

    stems = [Path(f).stem for f in filenames]
    prefix = _common_prefix(stems)
    separator = _detect_separator(stems)
    date_format = _detect_date_format(stems)

    return FolderPattern(
        prefix=prefix,
        separator=separator,
        date_format=date_format,
        examples=filenames[:5],
    )


def _common_prefix(stems: list[str]) -> str:
    """Find common prefix among filename stems."""
    if not stems:
        return ""
    if len(stems) == 1:
        for sep in ["_", "-", " "]:
            if sep in stems[0]:
                parts = stems[0].split(sep)
                return sep.join(parts[:-1]) + sep
        return ""

    prefix = stems[0]
    for s in stems[1:]:
        while not s.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    if not prefix:
        return ""

    for sep in ["_", "-", " "]:
        idx = prefix.rfind(sep)
        if idx > 0:
            return prefix[: idx + 1]

    if len(prefix) >= 3:
        count = sum(1 for s in stems if s.startswith(prefix))
        if count >= len(stems) * 0.5:
            return prefix

    return ""


def _detect_separator(stems: list[str]) -> str:
    """Detect most common separator in filenames."""
    counts = Counter()
    for s in stems:
        for sep in ["_", "-", " "]:
            counts[sep] += s.count(sep)
    if counts:
        return counts.most_common(1)[0][0]
    return "_"


def _detect_date_format(stems: list[str]) -> str:
    """Detect most common date format in filenames."""
    format_counts = Counter()
    for s in stems:
        if re.search(r"\d{4}-\d{2}-\d{2}", s):
            format_counts["YYYY-MM-DD"] += 1
        elif re.search(r"\d{2}\.\d{2}\.\d{4}", s):
            format_counts["DD.MM.YYYY"] += 1
        elif re.search(r"\d{4}_\d{2}_\d{2}", s):
            format_counts["YYYY_MM_DD"] += 1
        elif re.search(r"\d{4}\d{2}\d{2}", s):
            format_counts["YYYYMMDD"] += 1
    if format_counts:
        return format_counts.most_common(1)[0][0]
    return "YYYY-MM-DD"


def _format_date(year: str, month: str, day: str, fmt: str) -> str:
    """Format a date according to the detected pattern format.

    If day is empty, only year-month is returned.
    """
    if not day:
        # Month-only: "YYYY-MM" style regardless of format
        if fmt == "YYYY_MM_DD":
            return f"{year}_{month}"
        return f"{year}-{month}"
    if fmt == "YYYY-MM-DD":
        return f"{year}-{month}-{day}"
    elif fmt == "DD.MM.YYYY":
        return f"{day}.{month}.{year}"
    elif fmt == "YYYY_MM_DD":
        return f"{year}_{month}_{day}"
    elif fmt == "YYYYMMDD":
        return f"{year}{month}{day}"
    return f"{year}-{month}-{day}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def propose_name(text: str, pattern: FolderPattern) -> str:
    """Propose a filename based on document text and folder patterns."""
    parts = []

    if pattern.prefix:
        parts.append(pattern.prefix.rstrip(pattern.separator))

    date_tuple = _extract_date(text)
    if date_tuple:
        year, month, day = date_tuple
        parts.append(_format_date(year, month, day, pattern.date_format))

    sender = _extract_sender(text)
    if sender:
        parts.append(_sanitize(sender, pattern.separator))

    ref = _extract_reference(text)
    if ref:
        parts.append(ref)

    if not parts:
        return "document"

    return pattern.separator.join(parts)


def guess_name(text: str) -> str:
    """Best-guess filename purely from document content.

    Combines: document type, sender, date, reference, amount.
    Uses underscore separator and YYYY-MM-DD dates.
    """
    sep = "_"
    parts = []

    doc_type = _extract_doc_type(text)
    if doc_type:
        parts.append(doc_type)

    sender = _extract_sender(text)
    if sender:
        parts.append(_sanitize(sender, sep))

    date_tuple = _extract_date(text)
    if date_tuple:
        year, month, day = date_tuple
        parts.append(_format_date(year, month, day, "YYYY-MM-DD"))

    ref = _extract_reference(text)
    if ref:
        parts.append(ref)

    # Only add amount if we don't already have a reference (avoid clutter)
    if not ref:
        amount = _extract_amount(text)
        if amount:
            parts.append(amount)

    if not parts:
        return "document"

    return sep.join(parts)
