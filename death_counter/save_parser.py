from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

HEADER_SIZE = 0x300
SLOT_COUNT = 10
SLOT_STRIDE = 0x280010
SLOT_CHECKSUM_SIZE = 0x10
SLOT_PAYLOAD_SIZE = 0x280000
ACTIVE_PROFILES_OFFSET = 0x1901D04
PROFILE_SUMMARIES_OFFSET = 0x1901D0E
PROFILE_SUMMARY_SIZE = 0x24C
MINIMUM_SAVE_SIZE = PROFILE_SUMMARIES_OFFSET + SLOT_COUNT * PROFILE_SUMMARY_SIZE

GA_ITEM_COUNT = 0x1400
GA_ITEM_WEAPON = 0x80000000
GA_ITEM_ASH_OF_WAR = 0xC0000000
MAX_VARIABLE_BLOCK_SIZE = 0x10000
MAX_PROJECTILES = 100_000
MAX_REGIONS = 10_000


class SaveFormatError(ValueError):
    """Raised when bytes do not match the expected Elden Ring save layout."""


@dataclass(frozen=True)
class CharacterSlot:
    slot: int
    name: str
    level: int
    seconds_played: int
    deaths: int
    hp: int
    max_hp: int
    base_max_hp: int


def _require_range(data: bytes, offset: int, size: int, context: str) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise SaveFormatError(
            f"{context} extends beyond the save file "
            f"(offset=0x{offset:X}, size=0x{size:X})"
        )


def _u8(data: bytes, offset: int, context: str) -> int:
    _require_range(data, offset, 1, context)
    return data[offset]


def _u32(data: bytes, offset: int, context: str) -> int:
    _require_range(data, offset, 4, context)
    return struct.unpack_from("<I", data, offset)[0]


def _utf16_name(data: bytes, offset: int, context: str) -> str:
    _require_range(data, offset, 32, context)
    raw = data[offset : offset + 32]
    try:
        return raw.decode("utf-16-le").split("\0", 1)[0]
    except UnicodeDecodeError as error:
        raise SaveFormatError(f"{context} is not valid UTF-16LE") from error


def _checked_advance(
    data: bytes, offset: int, size: int, limit: int, context: str
) -> int:
    new_offset = offset + size
    if size < 0 or new_offset > limit or new_offset > len(data):
        raise SaveFormatError(
            f"{context} exceeds its character slot "
            f"(offset=0x{offset:X}, size=0x{size:X})"
        )
    return new_offset


def _validate_slot_checksum(data: bytes, slot_start: int, slot_number: int) -> None:
    expected = data[slot_start : slot_start + SLOT_CHECKSUM_SIZE]
    payload_start = slot_start + SLOT_CHECKSUM_SIZE
    _require_range(
        data,
        payload_start,
        SLOT_PAYLOAD_SIZE,
        f"slot {slot_number} checksum payload",
    )
    actual = hashlib.md5(
        data[payload_start : payload_start + SLOT_PAYLOAD_SIZE]
    ).digest()
    if actual != expected:
        raise SaveFormatError(
            f"slot {slot_number} checksum does not match; "
            "the game may still be writing the save"
        )


def _read_death_count(
    data: bytes, slot_start: int, slot_number: int
) -> tuple[int, int, int, int]:
    slot_end = slot_start + SLOT_STRIDE
    _require_range(data, slot_start, SLOT_STRIDE, f"slot {slot_number}")

    offset = slot_start + 0x30
    for item_index in range(GA_ITEM_COUNT):
        handle = _u32(data, offset, f"slot {slot_number} GA item {item_index}")
        offset = _checked_advance(
            data, offset, 8, slot_end, f"slot {slot_number} GA item"
        )
        handle_type = handle & 0xF0000000
        if handle != 0 and handle_type != GA_ITEM_ASH_OF_WAR:
            offset = _checked_advance(
                data, offset, 8, slot_end, f"slot {slot_number} GA item data"
            )
            if handle_type == GA_ITEM_WEAPON:
                offset = _checked_advance(
                    data,
                    offset,
                    5,
                    slot_end,
                    f"slot {slot_number} weapon data",
                )

    character_start = offset
    hp = _u32(data, character_start + 0x08, f"slot {slot_number} HP")
    max_hp = _u32(data, character_start + 0x0C, f"slot {slot_number} max HP")
    base_max_hp = _u32(
        data, character_start + 0x10, f"slot {slot_number} base max HP"
    )

    offset = _checked_advance(
        data, character_start, 0xB4, slot_end, f"slot {slot_number} character"
    )
    offset = _checked_advance(data, offset, 2, slot_end, "name terminator")
    offset = _checked_advance(data, offset, 10, slot_end, "character settings")
    offset = _checked_advance(data, offset, 0x18, slot_end, "character data")
    offset = _checked_advance(data, offset, 0x21, slot_end, "online settings")
    offset = _checked_advance(data, offset, 2, slot_end, "flask counts")
    offset = _checked_advance(data, offset, 0x15, slot_end, "flask data")
    offset = _checked_advance(data, offset, 6 * 18, slot_end, "group passwords")
    offset = _checked_advance(data, offset, 0x34, slot_end, "character padding")
    offset = _checked_advance(data, offset, 13 * 16, slot_end, "SP effects")
    offset = _checked_advance(data, offset, 88, slot_end, "equipment indices")
    offset = _checked_advance(data, offset, 28, slot_end, "weapon slots")
    offset = _checked_advance(data, offset, 88, slot_end, "equipment IDs")
    offset = _checked_advance(data, offset, 88, slot_end, "equipment handles")
    offset = _checked_advance(
        data,
        offset,
        16 + 12 * 2688 + 12 * 384,
        slot_end,
        "inventory",
    )
    offset = _checked_advance(data, offset, 116, slot_end, "equipped spells")
    offset = _checked_advance(data, offset, 140, slot_end, "equipped items")
    offset = _checked_advance(data, offset, 24, slot_end, "equipped gestures")

    projectile_count = _u32(data, offset, f"slot {slot_number} projectile count")
    if projectile_count > MAX_PROJECTILES:
        raise SaveFormatError(
            f"slot {slot_number} has an invalid projectile count "
            f"({projectile_count})"
        )
    offset = _checked_advance(
        data,
        offset,
        4 + projectile_count * 8,
        slot_end,
        "acquired projectiles",
    )
    offset = _checked_advance(data, offset, 156, slot_end, "equipped armaments")
    offset = _checked_advance(data, offset, 12, slot_end, "equipped physics")
    offset = _checked_advance(data, offset, 303, slot_end, "face data")
    offset = _checked_advance(
        data,
        offset,
        16 + 12 * 0x780 + 12 * 0x80,
        slot_end,
        "inventory storage",
    )
    offset = _checked_advance(data, offset, 256, slot_end, "gestures")

    region_count = _u32(data, offset, f"slot {slot_number} region count")
    if region_count > MAX_REGIONS:
        raise SaveFormatError(
            f"slot {slot_number} has an invalid region count ({region_count})"
        )
    offset = _checked_advance(
        data, offset, 4 + region_count * 4, slot_end, "regions"
    )
    offset = _checked_advance(data, offset, 40, slot_end, "Torrent data")
    offset = _checked_advance(data, offset, 1, slot_end, "control byte")
    offset = _checked_advance(data, offset, 68, slot_end, "bloodstain")
    offset = _checked_advance(data, offset, 8, slot_end, "unknown fields")
    offset = _checked_advance(data, offset, 4, slot_end, "menu save/load header")

    menu_size = _u32(data, offset, f"slot {slot_number} menu save/load size")
    if menu_size > MAX_VARIABLE_BLOCK_SIZE:
        raise SaveFormatError(
            f"slot {slot_number} has an invalid menu save/load size "
            f"({menu_size})"
        )
    offset = _checked_advance(
        data, offset, 4 + menu_size, slot_end, "menu save/load data"
    )
    offset = _checked_advance(data, offset, 52, slot_end, "trophy equipment")
    offset = _checked_advance(data, offset, 0x1B588, slot_end, "game item data")
    offset = _checked_advance(data, offset, 4, slot_end, "tutorial header")

    tutorial_size = _u32(data, offset, f"slot {slot_number} tutorial data size")
    if tutorial_size > MAX_VARIABLE_BLOCK_SIZE:
        raise SaveFormatError(
            f"slot {slot_number} has an invalid tutorial data size "
            f"({tutorial_size})"
        )
    offset = _checked_advance(
        data, offset, 4 + tutorial_size, slot_end, "tutorial data"
    )
    offset = _checked_advance(data, offset, 3, slot_end, "death count prefix")

    deaths = _u32(data, offset, f"slot {slot_number} death count")
    return deaths, hp, max_hp, base_max_hp


def parse_save(data: bytes, *, validate_checksums: bool = True) -> list[CharacterSlot]:
    """Parse active character slots from an ER0000.sl2 byte string."""
    if len(data) < MINIMUM_SAVE_SIZE:
        raise SaveFormatError(
            f"save is too small ({len(data)} bytes; expected at least "
            f"{MINIMUM_SAVE_SIZE})"
        )
    if data[:4] not in (b"BND4", b"SL2\0"):
        raise SaveFormatError(
            f"unsupported save signature {data[:4]!r}; expected BND4 or SL2\\0"
        )

    characters: list[CharacterSlot] = []
    for index in range(SLOT_COUNT):
        if _u8(
            data,
            ACTIVE_PROFILES_OFFSET + index,
            f"active-profile flag {index + 1}",
        ) != 1:
            continue

        summary = PROFILE_SUMMARIES_OFFSET + index * PROFILE_SUMMARY_SIZE
        name = _utf16_name(data, summary, f"slot {index + 1} profile name")
        if not name:
            raise SaveFormatError(f"active slot {index + 1} has no character name")
        level = _u32(data, summary + 0x22, f"slot {index + 1} profile level")
        seconds_played = _u32(
            data, summary + 0x26, f"slot {index + 1} play time"
        )

        slot_start = HEADER_SIZE + index * SLOT_STRIDE
        if validate_checksums:
            _validate_slot_checksum(data, slot_start, index + 1)
        deaths, hp, max_hp, base_max_hp = _read_death_count(
            data, slot_start, index + 1
        )
        characters.append(
            CharacterSlot(
                slot=index + 1,
                name=name,
                level=level,
                seconds_played=seconds_played,
                deaths=deaths,
                hp=hp,
                max_hp=max_hp,
                base_max_hp=base_max_hp,
            )
        )

    if not characters:
        raise SaveFormatError("the save does not contain any active characters")
    return characters


def parse_save_file(
    path: Path, *, validate_checksums: bool = True
) -> list[CharacterSlot]:
    return parse_save(path.read_bytes(), validate_checksums=validate_checksums)
