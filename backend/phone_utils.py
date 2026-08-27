"""Phone number normalization and validation shared by all API routes."""
import re


# Common country coverage for the UI and API. Lengths are national significant
# number lengths (country code excluded), not formatted display lengths.
COUNTRY_PHONE_RULES = {
    "91": {"name": "India", "lengths": {10}},
    "1": {"name": "United States / Canada", "lengths": {10}},
    "44": {"name": "United Kingdom", "lengths": {10}},
    "61": {"name": "Australia", "lengths": {9}},
    "971": {"name": "United Arab Emirates", "lengths": {9}},
    "65": {"name": "Singapore", "lengths": {8}},
    "60": {"name": "Malaysia", "lengths": {9, 10}},
    "49": {"name": "Germany", "lengths": {10, 11}},
    "33": {"name": "France", "lengths": {9}},
    "39": {"name": "Italy", "lengths": {9, 10}},
    "34": {"name": "Spain", "lengths": {9}},
    "81": {"name": "Japan", "lengths": {10}},
    "86": {"name": "China", "lengths": {11}},
    "64": {"name": "New Zealand", "lengths": {9}},
    "27": {"name": "South Africa", "lengths": {9}},
    "966": {"name": "Saudi Arabia", "lengths": {9}},
    "974": {"name": "Qatar", "lengths": {8}},
    "880": {"name": "Bangladesh", "lengths": {10}},
    "977": {"name": "Nepal", "lengths": {10}},
    "94": {"name": "Sri Lanka", "lengths": {9}},
}

_SORTED_CODES = sorted(COUNTRY_PHONE_RULES, key=len, reverse=True)


class PhoneValidationError(ValueError):
    """Raised when a phone cannot be safely normalized or validated."""


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_phone(value: str, default_country_code: str = "91") -> str:
    """Return canonical E.164-like form, treating bare numbers as India."""
    raw = (value or "").strip()
    digits = _digits(raw)
    if raw.startswith("00"):
        digits = digits[2:]
    elif not raw.startswith("+"):
        # Existing records and legacy UI values without a country code are India.
        if len(digits) == 10:
            digits = default_country_code + digits
        elif digits.startswith(default_country_code) and len(digits) > 10:
            digits = digits
        else:
            digits = default_country_code + digits
    if not digits:
        return ""
    return f"+{digits}"


def phone_parts(value: str, default_country_code: str = "91") -> tuple[str, str]:
    canonical = normalize_phone(value, default_country_code)
    digits = canonical[1:] if canonical.startswith("+") else canonical
    code = next((candidate for candidate in _SORTED_CODES if digits.startswith(candidate)), default_country_code)
    return code, digits[len(code):]


def validate_phone(value: str, default_country_code: str = "91") -> str:
    """Normalize and validate a phone; raises a user-safe validation error."""
    canonical = normalize_phone(value, default_country_code)
    if not canonical:
        raise PhoneValidationError("Please enter a mobile number")
    code, local = phone_parts(canonical, default_country_code)
    rule = COUNTRY_PHONE_RULES.get(code)
    if not rule:
        raise PhoneValidationError("Please select a supported country code")
    if len(local) not in rule["lengths"]:
        expected = "/".join(str(n) for n in sorted(rule["lengths"]))
        raise PhoneValidationError(f"Mobile number must contain {expected} digits for {rule['name']}")
    if len(set(local)) == 1:
        raise PhoneValidationError("Mobile number cannot contain the same digit repeatedly")
    return canonical


def phone_variants(value: str, default_country_code: str = "91") -> list[str]:
    """Canonical + legacy bare variants for matching pre-normalization records."""
    canonical = normalize_phone(value, default_country_code)
    if not canonical:
        return []
    code, local = phone_parts(canonical, default_country_code)
    return list(dict.fromkeys([canonical, local, canonical[1:]]))
