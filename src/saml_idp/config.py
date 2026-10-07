"""Loading and validation of the IdP's JSON configuration file."""

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any


DEFAULT_ASSERTION_LIFETIME_SECONDS = 300
DEFAULT_ATTRIBUTE_NAMES = {
    "email": "email",
    "firstName": "first_name",
    "lastName": "last_name",
}

_MISSING = object()

logger = logging.getLogger(__name__)


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


@dataclass(frozen=True)
class User:
    email: str
    first_name: str
    last_name: str

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class ServiceProvider:
    entity_id: str
    acs_url: str
    allow_request_acs_url: bool


@dataclass(frozen=True)
class AttributeNames:
    """SAML attribute names for each user field; ``None`` omits the attribute."""

    email: str | None
    first_name: str | None
    last_name: str | None

    def values_for(self, user: User) -> dict[str, str]:
        pairs = (
            (self.email, user.email),
            (self.first_name, user.first_name),
            (self.last_name, user.last_name),
        )
        return {name: value for name, value in pairs if name}


@dataclass(frozen=True)
class Config:
    sp: ServiceProvider
    users: tuple[User, ...]
    attribute_names: AttributeNames
    base_url: str | None
    entity_id: str | None
    sign_response: bool
    sign_assertion: bool
    assertion_lifetime: timedelta

    def find_user(self, email: str) -> User | None:
        return next((u for u in self.users if u.email == email), None)


def _get(
    data: dict[str, Any], key: str, kind: type, context: str, default: Any = _MISSING
) -> Any:
    value = data.get(key)
    if value is None or (kind is str and value == ""):
        if default is _MISSING:
            raise ConfigError(f"{context}{key} is required")
        return default
    # bool is a subclass of int, so reject it explicitly for integer fields.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ConfigError(f"{context}{key} must be a {kind.__name__}, got {value!r}")
    return value


def _optional_str(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{context}{key} must be a string, got {value!r}")
    return value


def _parse_user(data: Any, index: int) -> User:
    context = f"users[{index}]."
    if not isinstance(data, dict):
        raise ConfigError(f"users[{index}] must be an object")
    return User(
        email=_get(data, "email", str, context),
        first_name=_get(data, "firstName", str, context),
        last_name=_get(data, "lastName", str, context),
    )


def parse_config(data: Any) -> Config:
    """Validate a decoded JSON document and turn it into a :class:`Config`."""
    if not isinstance(data, dict):
        raise ConfigError("configuration must be a JSON object")

    sp_data = _get(data, "sp", dict, "")
    sp = ServiceProvider(
        entity_id=_get(sp_data, "entityId", str, "sp."),
        acs_url=_get(sp_data, "acsUrl", str, "sp."),
        allow_request_acs_url=_get(sp_data, "allowRequestAcsUrl", bool, "sp.", False),
    )

    users_data = _get(data, "users", list, "")
    users = tuple(_parse_user(u, i) for i, u in enumerate(users_data))
    if not users:
        raise ConfigError("users must contain at least one user")
    emails = [u.email for u in users]
    duplicates = sorted({e for e in emails if emails.count(e) > 1})
    if duplicates:
        raise ConfigError(f"users contains duplicate emails: {', '.join(duplicates)}")

    names_data = {
        **DEFAULT_ATTRIBUTE_NAMES,
        **_get(data, "attributeNames", dict, "", {}),
    }
    attribute_names = AttributeNames(
        email=_optional_str(names_data, "email", "attributeNames."),
        first_name=_optional_str(names_data, "firstName", "attributeNames."),
        last_name=_optional_str(names_data, "lastName", "attributeNames."),
    )

    lifetime = _get(
        data, "assertionLifetimeSeconds", int, "", DEFAULT_ASSERTION_LIFETIME_SECONDS
    )
    if lifetime <= 0:
        raise ConfigError("assertionLifetimeSeconds must be positive")

    base_url = _optional_str(data, "baseUrl", "")
    return Config(
        sp=sp,
        users=users,
        attribute_names=attribute_names,
        base_url=base_url.rstrip("/") if base_url else None,
        entity_id=_optional_str(data, "entityId", ""),
        sign_response=_get(data, "signResponse", bool, "", True),
        sign_assertion=_get(data, "signAssertion", bool, "", True),
        assertion_lifetime=timedelta(seconds=lifetime),
    )


def load_config(path: Path) -> Config:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}")
    return parse_config(data)


class ConfigStore:
    """
    Serves the current configuration, reloading it whenever the file changes.

    Kubernetes updates mounted ConfigMaps in place, so this lets user and SP
    changes take effect without restarting the pod (which would regenerate the
    signing certificates).  If a changed file is invalid, the last good
    configuration stays in use.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._config = load_config(path)
        self._mtime = path.stat().st_mtime_ns

    def get(self) -> Config:
        try:
            mtime = self._path.stat().st_mtime_ns
        except OSError as e:
            logger.warning("Cannot stat %s, keeping previous config: %s", self._path, e)
            return self._config
        if mtime != self._mtime:
            self._mtime = mtime
            try:
                self._config = load_config(self._path)
                logger.info("Reloaded configuration from %s", self._path)
            except ConfigError as e:
                logger.error("Invalid configuration, keeping previous config: %s", e)
        return self._config
