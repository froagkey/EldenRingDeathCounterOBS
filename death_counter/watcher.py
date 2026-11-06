from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .save_parser import CharacterSlot, SaveFormatError, parse_save


class CounterConfigurationError(ValueError):
    """Raised when the requested save or character cannot be selected."""


@dataclass(frozen=True)
class WatchOptions:
    save_path: Path
    output_path: Path
    slot: int | None = None
    character: str | None = None
    output_format: str = "{deaths}"
    poll_interval: float = 0.25
    settle_time: float = 0.75
    read_attempts: int = 5
    retry_delay: float = 0.2


def discover_save(appdata: Path | None = None) -> Path:
    root = (appdata or Path(os.environ.get("APPDATA", ""))) / "EldenRing"
    candidates = sorted(root.glob("*/ER0000.sl2")) if root.is_dir() else []
    if not candidates:
        raise CounterConfigurationError(
            f"no ER0000.sl2 was found under {root}; pass --save explicitly"
        )
    if len(candidates) > 1:
        paths = "\n".join(f"  {path}" for path in candidates)
        raise CounterConfigurationError(
            "multiple Elden Ring saves were found; pass --save explicitly:\n"
            f"{paths}"
        )
    return candidates[0]


def read_stable_save(path: Path) -> bytes:
    try:
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
    except OSError as error:
        raise SaveFormatError(f"could not read {path}: {error}") from error

    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != after.st_size
    ):
        raise SaveFormatError("the save changed while it was being read")
    return data


def select_character(
    characters: list[CharacterSlot],
    *,
    slot: int | None = None,
    character: str | None = None,
) -> CharacterSlot:
    if slot is not None:
        for candidate in characters:
            if candidate.slot == slot:
                return candidate
        raise CounterConfigurationError(f"slot {slot} is not active")

    if character is not None:
        matches = [
            candidate
            for candidate in characters
            if candidate.name.casefold() == character.casefold()
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise CounterConfigurationError(
                f"no active character is named {character!r}"
            )
        raise CounterConfigurationError(
            f"more than one active character is named {character!r}; use --slot"
        )

    if len(characters) == 1:
        return characters[0]
    choices = "\n".join(
        f"  --slot {candidate.slot}: {candidate.name} "
        f"(level {candidate.level}, {candidate.deaths} deaths)"
        for candidate in characters
    )
    raise CounterConfigurationError(
        "the save has multiple active characters; select one:\n" f"{choices}"
    )


def render_output(template: str, character: CharacterSlot) -> str:
    try:
        return template.format(
            deaths=character.deaths,
            name=character.name,
            slot=character.slot,
            level=character.level,
            hp=character.hp,
            max_hp=character.max_hp,
            base_max_hp=character.base_max_hp,
        )
    except (KeyError, ValueError) as error:
        raise CounterConfigurationError(
            f"invalid --format value {template!r}: {error}"
        ) from error


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_character(options: WatchOptions) -> CharacterSlot:
    last_error: SaveFormatError | CounterConfigurationError | None = None
    for attempt in range(options.read_attempts):
        try:
            data = read_stable_save(options.save_path)
            characters = parse_save(data)
            return select_character(
                characters, slot=options.slot, character=options.character
            )
        except (SaveFormatError, CounterConfigurationError) as error:
            last_error = error
            if attempt + 1 < options.read_attempts:
                time.sleep(options.retry_delay)
    assert last_error is not None
    raise last_error


def watch(
    options: WatchOptions,
    *,
    on_update: Callable[[CharacterSlot, str], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    last_signature: tuple[int, int] | None = None
    last_change_at = 0.0
    last_output: str | None = None
    pending = True

    while True:
        try:
            stat = options.save_path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except OSError as error:
            if on_error:
                on_error(error)
            time.sleep(options.poll_interval)
            continue

        now = time.monotonic()
        if signature != last_signature:
            last_signature = signature
            last_change_at = now
            pending = True

        if pending and now - last_change_at >= options.settle_time:
            try:
                selected = read_character(options)
                rendered = render_output(options.output_format, selected)
                if rendered != last_output:
                    write_text_atomic(options.output_path, rendered)
                    last_output = rendered
                    if on_update:
                        on_update(selected, rendered)
                pending = False
            except (
                OSError,
                SaveFormatError,
                CounterConfigurationError,
            ) as error:
                if on_error:
                    on_error(error)
                last_change_at = time.monotonic()

        time.sleep(options.poll_interval)
