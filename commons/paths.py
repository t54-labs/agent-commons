"""Filesystem path helpers for Commons."""

from __future__ import annotations

import os
from pathlib import Path


def commons_home() -> Path:
    return Path(os.environ.get("COMMONS_HOME", "~/.commons")).expanduser()


def state_dir() -> Path:
    return commons_home() / "state"


def artifact_dir() -> Path:
    return commons_home() / "artifacts"


def runtime_tests_dir() -> Path:
    return commons_home() / "runtime-tests"


def relay_dir() -> Path:
    return commons_home() / "relay"


def board_dir() -> Path:
    return commons_home() / "board"


def log_dir() -> Path:
    return commons_home() / "logs"


def bin_dir() -> Path:
    return commons_home() / "bin"


def config_path() -> Path:
    return commons_home() / "config.toml"


def db_path() -> Path:
    return state_dir() / "commons.db"


def relay_db_path() -> Path:
    return Path(os.environ.get("COMMONS_RELAY_DB", str(relay_dir() / "relay.db"))).expanduser()


def remote_config_path() -> Path:
    return commons_home() / "remotes.json"


def user_config_path() -> Path:
    return commons_home() / "user.json"


def pid_path() -> Path:
    return commons_home() / "commonsd.pid"


def ensure_base_dirs() -> None:
    # The local filesystem board is opt-in state. board.ensure_board() creates
    # it only after local mode is selected or a local operation needs it.
    for path in (commons_home(), state_dir(), artifact_dir(), runtime_tests_dir(), relay_dir(), log_dir(), bin_dir()):
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except PermissionError:
            pass
