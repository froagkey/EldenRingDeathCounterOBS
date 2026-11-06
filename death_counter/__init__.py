"""Elden Ring death counter for OBS."""

from .save_parser import CharacterSlot, SaveFormatError, parse_save

__all__ = ["CharacterSlot", "SaveFormatError", "parse_save"]
