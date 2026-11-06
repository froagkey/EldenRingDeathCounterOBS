from __future__ import annotations

import hashlib
import struct

from death_counter.save_parser import (
    ACTIVE_PROFILES_OFFSET,
    HEADER_SIZE,
    MINIMUM_SAVE_SIZE,
    PROFILE_SUMMARIES_OFFSET,
    PROFILE_SUMMARY_SIZE,
    SLOT_PAYLOAD_SIZE,
    SLOT_STRIDE,
)


def make_save(
    *,
    slot: int = 1,
    name: str = "Tarnished",
    level: int = 150,
    seconds_played: int = 12_345,
    deaths: int = 321,
    hp: int = 1_234,
    max_hp: int = 1_900,
    base_max_hp: int = 1_900,
    projectile_count: int = 2,
    region_count: int = 3,
    menu_size: int = 17,
    tutorial_size: int = 23,
) -> bytes:
    index = slot - 1
    data = bytearray(MINIMUM_SAVE_SIZE)
    data[:4] = b"BND4"

    data[ACTIVE_PROFILES_OFFSET + index] = 1
    summary = PROFILE_SUMMARIES_OFFSET + index * PROFILE_SUMMARY_SIZE
    encoded_name = name.encode("utf-16-le")
    data[summary : summary + len(encoded_name)] = encoded_name
    struct.pack_into("<I", data, summary + 0x22, level)
    struct.pack_into("<I", data, summary + 0x26, seconds_played)

    slot_start = HEADER_SIZE + index * SLOT_STRIDE
    character_start = slot_start + 0x30 + 0x1400 * 8
    struct.pack_into("<I", data, character_start + 0x08, hp)
    struct.pack_into("<I", data, character_start + 0x0C, max_hp)
    struct.pack_into("<I", data, character_start + 0x10, base_max_hp)

    offset = character_start
    offset += 0xB4
    offset += 2
    offset += 10
    offset += 0x18
    offset += 0x21
    offset += 2
    offset += 0x15
    offset += 6 * 18
    offset += 0x34
    offset += 13 * 16
    offset += 88
    offset += 28
    offset += 88
    offset += 88
    offset += 16 + 12 * 2688 + 12 * 384
    offset += 116
    offset += 140
    offset += 24
    struct.pack_into("<I", data, offset, projectile_count)
    offset += 4 + projectile_count * 8
    offset += 156
    offset += 12
    offset += 303
    offset += 16 + 12 * 0x780 + 12 * 0x80
    offset += 256
    struct.pack_into("<I", data, offset, region_count)
    offset += 4 + region_count * 4
    offset += 40
    offset += 1
    offset += 68
    offset += 8
    offset += 4
    struct.pack_into("<I", data, offset, menu_size)
    offset += 4 + menu_size
    offset += 52
    offset += 0x1B588
    offset += 4
    struct.pack_into("<I", data, offset, tutorial_size)
    offset += 4 + tutorial_size
    offset += 3
    struct.pack_into("<I", data, offset, deaths)

    payload_start = slot_start + 0x10
    checksum = hashlib.md5(
        data[payload_start : payload_start + SLOT_PAYLOAD_SIZE]
    ).digest()
    data[slot_start : slot_start + 0x10] = checksum
    return bytes(data)
