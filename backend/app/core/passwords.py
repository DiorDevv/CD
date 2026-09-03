"""Yagona parol siyosati — barcha joyda (seed, admin create, change-password) shu ishlatiladi."""

import secrets

from app.config import settings

_LOWER = "abcdefghijkmnpqrstuvwxyz"
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_DIGIT = "23456789"
_SYMBOL = "!@#$%^&*"

# Eng ko'p uchraydigan / zaif parollar (qisqa ro'yxat — to'liq lug'at o'rniga minimal himoya)
_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passw0rd",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty123",
        "qwertyuiop",
        "adminadmin",
        "administrator",
        "welcome1",
        "welcome123",
        "changeme",
        "changeme123",
        "letmein123",
        "iloveyou1",
        "superadmin",
        "soc_admin1",
        "dlp_admin1",
    }
)


class PasswordPolicyError(ValueError):
    """Parol siyosatga mos kelmaganda."""


def validate_password_strength(password: str, *, username: str | None = None) -> None:
    """Parolni tekshiradi. Mos bo'lmasa PasswordPolicyError (ValueError) ko'taradi."""
    min_len = settings.PASSWORD_MIN_LENGTH

    if len(password) < min_len:
        raise PasswordPolicyError(f"Parol kamida {min_len} ta belgidan iborat bo'lishi kerak")
    if len(password) > 128:
        raise PasswordPolicyError("Parol 128 ta belgidan uzun bo'lmasligi kerak")
    if password.strip() != password:
        raise PasswordPolicyError("Parol boshida yoki oxirida bo'sh joy bo'lmasligi kerak")
    if any(ch.isspace() for ch in password):
        raise PasswordPolicyError("Parolda bo'sh joy belgilar bo'lmasligi kerak")
    if not any(ch.islower() for ch in password):
        raise PasswordPolicyError("Parolda kamida bitta kichik harf bo'lishi kerak")
    if not any(ch.isupper() for ch in password):
        raise PasswordPolicyError("Parolda kamida bitta katta harf bo'lishi kerak")
    if not any(ch.isdigit() for ch in password):
        raise PasswordPolicyError("Parolda kamida bitta raqam bo'lishi kerak")
    if password.lower() in _COMMON_PASSWORDS:
        raise PasswordPolicyError("Bu parol juda oddiy — boshqa parol tanlang")
    if username and username.lower() in password.lower():
        raise PasswordPolicyError("Parol foydalanuvchi nomini o'z ichiga olmasligi kerak")
    # bir xil belgining ketma-ket 4+ takrori
    if any(password[i] == password[i + 1] == password[i + 2] == password[i + 3]
           for i in range(len(password) - 3)):
        raise PasswordPolicyError("Parolda bir belgi 4 martadan ko'p ketma-ket takrorlanmasin")


def generate_temp_password(length: int | None = None) -> str:
    """Siyosatga kafolatli mos vaqtinchalik parol yaratadi."""
    n = max(length or (settings.PASSWORD_MIN_LENGTH + 4), settings.PASSWORD_MIN_LENGTH + 2)
    chars = [
        secrets.choice(_UPPER),
        secrets.choice(_UPPER),
        secrets.choice(_LOWER),
        secrets.choice(_LOWER),
        secrets.choice(_DIGIT),
        secrets.choice(_DIGIT),
        secrets.choice(_SYMBOL),
    ]
    pool = _LOWER + _UPPER + _DIGIT
    while len(chars) < n:
        chars.append(secrets.choice(pool))
    # Fisher–Yates aralashtirish
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    pw = "".join(chars)
    validate_password_strength(pw)  # ehtiyot chorasi
    return pw
