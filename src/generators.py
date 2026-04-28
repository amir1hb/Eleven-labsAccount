"""Random username, password, and name generators."""
from __future__ import annotations

import secrets
import string

USERNAME_ALPHABET = string.ascii_lowercase + string.digits
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%"

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery",
    "Quinn", "Sam", "Drew", "Reese", "Skyler", "Cameron", "Hayden",
    "Parker", "Rowan", "Sage", "Emerson", "Finley", "Harper",
]
LAST_NAMES = [
    "Smith", "Johnson", "Brown", "Davis", "Miller", "Wilson", "Moore",
    "Taylor", "Anderson", "Thomas", "Harris", "Clark", "Lewis", "Walker",
    "Hall", "Young", "King", "Wright", "Lopez", "Hill",
]

# Common USA male first names — used for ElevenLabs onboarding's firstname
# field (placeholder is "William"). 50 most common per US SSA records.
USA_MALE_FIRST_NAMES = [
    "Liam", "Noah", "Oliver", "James", "Elijah", "William", "Henry", "Lucas",
    "Benjamin", "Theodore", "Mason", "Ethan", "Levi", "Daniel", "Jacob",
    "Logan", "Jackson", "Michael", "Alexander", "Sebastian", "Owen", "Asher",
    "Samuel", "Aiden", "John", "David", "Matthew", "Joseph", "Andrew",
    "Anthony", "Christopher", "Joshua", "Ryan", "Nathan", "Caleb", "Isaac",
    "Luke", "Wyatt", "Jonathan", "Charles", "Thomas", "Eli", "Connor",
    "Adrian", "Nicholas", "Dylan", "Aaron", "Brandon", "Justin", "Cameron",
]


def random_username(length: int = 10) -> str:
    return "".join(secrets.choice(USERNAME_ALPHABET) for _ in range(length))


def random_password(length: int = 16) -> str:
    """Generate a strong random password.

    Guarantees at least one of each: lowercase, uppercase, digit, symbol.
    """
    if length < 8:
        raise ValueError("password length must be >= 8")
    lower = secrets.choice(string.ascii_lowercase)
    upper = secrets.choice(string.ascii_uppercase)
    digit = secrets.choice(string.digits)
    symbol = secrets.choice("!@#$%")
    rest = [secrets.choice(PASSWORD_ALPHABET) for _ in range(length - 4)]
    chars = [lower, upper, digit, symbol, *rest]
    # Shuffle securely.
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def random_name() -> tuple[str, str]:
    return secrets.choice(FIRST_NAMES), secrets.choice(LAST_NAMES)


def random_full_name() -> str:
    first, last = random_name()
    return f"{first} {last}"


def random_usa_male_first_name() -> str:
    """A common USA male first name. Used for ElevenLabs onboarding."""
    return secrets.choice(USA_MALE_FIRST_NAMES)


def pick_domain(domains: list[str], skip: set[str] | None = None) -> str | None:
    """Pick a random domain not in `skip`. Returns None if all are skipped."""
    skip = skip or set()
    candidates = [d for d in domains if d not in skip]
    if not candidates:
        return None
    return secrets.choice(candidates)
