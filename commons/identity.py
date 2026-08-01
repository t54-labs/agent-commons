"""Persistent human identity and Agent naming helpers."""

from __future__ import annotations

import json
import os
import unicodedata
from typing import Any

from .paths import ensure_base_dirs, user_config_path
from .service import CommonsError


MAX_USER_NAME_LENGTH = 64
MAX_USER_SLUG_LENGTH = 24
MAX_AGENT_HANDLE_LENGTH = 48
MAX_AGENT_NAME_LENGTH = 96


class IdentityError(CommonsError):
    """A stable, actionable local identity failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        remediation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source = "commons-cli"
        self.remediation = remediation
        self.details = details or {}


def normalize_user_name(name: str | None) -> str:
    value = unicodedata.normalize("NFKC", str(name or ""))
    value = " ".join(value.split())
    if not value:
        raise IdentityError(
            "Commons user name is required",
            code="user_name_required",
            remediation='Ask the user for their name, then run: commons user set --name "<name>".',
        )
    if len(value) > MAX_USER_NAME_LENGTH:
        raise IdentityError(
            "Commons user name is too long",
            code="invalid_user_name",
            details={"maximum_length": MAX_USER_NAME_LENGTH},
            remediation=f"Use a name no longer than {MAX_USER_NAME_LENGTH} characters.",
        )
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise IdentityError(
            "Commons user name contains unsupported control characters",
            code="invalid_user_name",
            remediation="Use a normal human-readable name without control characters.",
        )
    return value


def user_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", normalize_user_name(name)).casefold()
    pieces: list[str] = []
    separator_pending = False
    for character in normalized:
        if character.isalnum():
            if separator_pending and pieces:
                pieces.append("-")
            pieces.append(character)
            separator_pending = False
        else:
            separator_pending = True
    slug = "".join(pieces).strip("-")[:MAX_USER_SLUG_LENGTH].rstrip("-")
    if not slug:
        raise IdentityError(
            "Commons user name cannot produce an Agent prefix",
            code="invalid_user_name",
            remediation="Use a name containing at least one letter or number.",
        )
    return slug


def profile_from_name(name: str, source: str = "config") -> dict[str, Any]:
    normalized = normalize_user_name(name)
    return {
        "configured": True,
        "name": normalized,
        "slug": user_slug(normalized),
        "source": source,
    }


def load_profile() -> dict[str, Any]:
    environment_name = os.environ.get("COMMONS_USER_NAME", "").strip()
    if environment_name:
        return profile_from_name(environment_name, "environment")
    path = user_config_path()
    if not path.exists():
        return {
            "configured": False,
            "name": None,
            "slug": None,
            "source": None,
            "config": str(path),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError(
            f"invalid Commons user config: {path}",
            code="invalid_user_config",
            remediation='Run: commons user set --name "<name>".',
        ) from exc
    if not isinstance(payload, dict):
        raise IdentityError(
            f"invalid Commons user config: {path}",
            code="invalid_user_config",
            remediation='Run: commons user set --name "<name>".',
        )
    profile = profile_from_name(payload.get("name"), "config")
    profile["config"] = str(path)
    return profile


def save_profile(name: str) -> dict[str, Any]:
    ensure_base_dirs()
    profile = profile_from_name(name, "config")
    path = user_config_path()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                {"version": 1, "name": profile["name"], "slug": profile["slug"]},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            temporary.chmod(0o600)
        except PermissionError:
            pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    profile["ok"] = True
    profile["config"] = str(path)
    return profile


def require_profile() -> dict[str, Any]:
    profile = load_profile()
    if not profile["configured"]:
        raise IdentityError(
            "Commons does not know the current user's name",
            code="user_name_required",
            details={"config": profile["config"]},
            remediation='Ask the user for their name, then run: commons user set --name "<name>".',
        )
    return profile


def normalize_agent_handle(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    cleaned = "".join(character for character in normalized if character.isalnum() or character in {"-", "_", "."})
    return cleaned.strip("-_.")


def qualify_handle(profile: dict[str, Any], proposed: str | None) -> str:
    slug = str(profile["slug"])
    candidate = normalize_agent_handle(proposed) or "agent"
    prefix = f"{slug}-"
    if candidate == slug:
        candidate = "agent"
    elif candidate.startswith(prefix):
        candidate = candidate[len(prefix):] or "agent"
    maximum_suffix = max(1, MAX_AGENT_HANDLE_LENGTH - len(prefix))
    suffix = candidate[:maximum_suffix].rstrip("-_.") or "agent"
    return f"{prefix}{suffix}"


def qualify_name(profile: dict[str, Any], proposed: str | None) -> str:
    display_name = str(profile["name"])
    slug = str(profile["slug"])
    candidate = unicodedata.normalize("NFKC", str(proposed or "agent")).strip().lstrip("@") or "agent"
    lowered = candidate.casefold()
    if lowered.startswith(f"{slug}-"):
        candidate = candidate[len(slug) + 1:] or "agent"
    elif lowered.startswith(f"{display_name.casefold()}-"):
        candidate = candidate[len(display_name) + 1:] or "agent"
    maximum_suffix = max(1, MAX_AGENT_NAME_LENGTH - len(display_name) - 1)
    return f"{display_name}-{candidate[:maximum_suffix]}"


def handle_has_user_prefix(handle: str | None, slug: str) -> bool:
    normalized = normalize_agent_handle(handle)
    return bool(normalized and normalized.startswith(f"{slug}-") and len(normalized) > len(slug) + 1)
