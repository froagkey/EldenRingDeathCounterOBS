from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .overlay import OverlayServer, OverlayState
from .save_parser import CharacterSlot, SaveFormatError, parse_save
from .watcher import (
    CounterConfigurationError,
    WatchOptions,
    discover_save,
    read_stable_save,
    render_output,
    select_character,
    watch,
)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _port(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return parsed


def _default_output_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("death_count.txt")
    return Path("death_count.txt")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously read an Elden Ring save and update an OBS text file."
        )
    )
    parser.add_argument(
        "--save",
        type=Path,
        help="path to ER0000.sl2; auto-discovered when omitted",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="OBS text-file destination (default: death_count.txt)",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--slot", type=int, choices=range(1, 11))
    selection.add_argument("--character", help="character name, case-insensitive")
    parser.add_argument(
        "--format",
        default="{deaths}",
        help=(
            "output template; fields: deaths, name, slot, level, hp, max_hp, "
            "base_max_hp (default: {deaths})"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=_positive_float,
        default=0.25,
        help="seconds between file checks (default: 0.25)",
    )
    parser.add_argument(
        "--settle-time",
        type=_positive_float,
        default=0.75,
        help="seconds the save must remain unchanged before reading (default: 0.75)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list active characters and exit",
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=8765,
        help="local OBS overlay port (default: 8765)",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="disable the local OBS Browser Source server",
    )
    return parser


def _print_characters(
    save_path: Path, characters: list[CharacterSlot] | None = None
) -> None:
    characters = characters or parse_save(read_stable_save(save_path))
    print(f"Save: {save_path}")
    for character in characters:
        hours, remainder = divmod(character.seconds_played, 3600)
        minutes = remainder // 60
        print(
            f"Slot {character.slot}: {character.name} | "
            f"level {character.level} | deaths {character.deaths} | "
            f"playtime {hours}h {minutes}m"
        )


def _prompt_for_character(
    characters: list[CharacterSlot],
) -> CharacterSlot:
    print("Active characters:")
    for candidate in characters:
        print(
            f"  Slot {candidate.slot}: {candidate.name} "
            f"(level {candidate.level}, {candidate.deaths} deaths)"
        )

    while True:
        response = input("Enter the slot number to watch: ").strip()
        try:
            slot = int(response)
        except ValueError:
            print("Enter a number from 1 to 10.")
            continue
        try:
            return select_character(characters, slot=slot)
        except CounterConfigurationError as error:
            print(error)


def _pause_frozen_console() -> None:
    if getattr(sys, "frozen", False) and sys.stdin.isatty():
        try:
            input("Press Enter to close.")
        except EOFError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    overlay_server: OverlayServer | None = None

    try:
        save_path = args.save.expanduser().resolve() if args.save else discover_save()
        characters = parse_save(read_stable_save(save_path))
        if args.list:
            _print_characters(save_path, characters)
            return 0

        if args.slot is not None or args.character is not None:
            selected = select_character(
                characters, slot=args.slot, character=args.character
            )
        elif len(characters) == 1:
            selected = characters[0]
        elif sys.stdin.isatty():
            selected = _prompt_for_character(characters)
        else:
            selected = select_character(characters)

        render_output(args.format, selected)
        output_path = args.output.expanduser().resolve()
        options = WatchOptions(
            save_path=save_path,
            output_path=output_path,
            slot=selected.slot,
            output_format=args.format,
            poll_interval=args.poll_interval,
            settle_time=args.settle_time,
        )
        overlay_state = OverlayState()
        overlay_state.update_character(selected)
        if not args.no_overlay:
            overlay_server = OverlayServer(overlay_state, port=args.port)
            overlay_server.start()

        print(f"Watching: {save_path}")
        print(
            f"Character: slot {selected.slot} ({selected.name}), "
            f"{selected.deaths} deaths"
        )
        print(f"OBS output: {output_path}")
        if overlay_server:
            print(f"OBS Browser Source: {overlay_server.url}")
        print("Press Ctrl+C to stop.")

        last_error: str | None = None

        def on_update(character, rendered: str) -> None:
            nonlocal last_error
            last_error = None
            overlay_state.update_character(character)
            print(
                f"Updated slot {character.slot} ({character.name}): "
                f"{rendered!r}",
                flush=True,
            )

        def on_error(error: Exception) -> None:
            nonlocal last_error
            message = str(error)
            if message != last_error:
                print(f"Waiting for a valid save: {message}", file=sys.stderr)
                last_error = message
            overlay_state.update_error(error)

        watch(options, on_update=on_update, on_error=on_error)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except (CounterConfigurationError, SaveFormatError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        _pause_frozen_console()
        return 2
    finally:
        if overlay_server:
            overlay_server.close()
    return 0
