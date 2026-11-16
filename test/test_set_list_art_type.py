#!/usr/bin/env python3
"""Test that a set list row's description gives the art type of its printings.

Magnificent Maestros prints Unchained Soul Lord of Yama twice: MAMS-EN100 with its
normal art, and MAMS-EN125 with extended art. Only the set list says EN124 and the
Starlight Rare of EN125 are extended arts: their galleries and files don't.

Run with `PYTHONPATH=src python test/test_set_list_art_type.py` (or with pytest).
"""
import uuid

import wikitextparser

from ygojson.database import *
from ygojson.importers.yugipedia import parse_tcg_ocg_set

SET_PAGE = """{{Infobox set
| en_name         = Magnificent Maestros
| na_release_date = November 13, 2026
}}

== Lists ==
{{Set navigation
| lists        = EN
| 1e_galleries = EN
}}
"""

SET_LIST = """{{Set page header}}

{{Set list|region=EN|rarities=Ultra Rare|print=Reprint|
MAMS-EN001; Blue-Eyes White Dragon, the White Phantom Beast;; New
MAMS-EN001; Blue-Eyes White Dragon, the White Phantom Beast; Ultra Rare, Starlight Rare; New // description::(extended art)
MAMS-EN100; Unchained Soul Lord of Yama
MAMS-EN124; Unchained Abomination; Ultra Rare, Starlight Rare; New artwork // description::(extended art)
MAMS-EN125; Unchained Soul Lord of Yama; Ultra Rare, Starlight Rare; New artwork // description::(extended art)
MAMS-EN126; Kuriboh Token; Common; New // description::(art)
}}
"""

SET_GALLERY = """{{Set page header}}

== Ultra Rares ==
{{Set gallery|rarity=Ultra Rare|
MAMS-EN001; Blue-Eyes White Dragon, the White Phantom Beast
MAMS-EN001; Blue-Eyes White Dragon, the White Phantom Beast;; EA
MAMS-EN100; Unchained Soul Lord of Yama
MAMS-EN124; Unchained Abomination
MAMS-EN125; Unchained Soul Lord of Yama;; EA
}}

== Starlight Rares ==
{{Set gallery|rarity=Starlight Rare|
MAMS-EN001; Blue-Eyes White Dragon, the White Phantom Beast
MAMS-EN124; Unchained Abomination
MAMS-EN125; Unchained Soul Lord of Yama
}}

== Commons ==
{{Set gallery|rarity=Common|
MAMS-EN126; Kuriboh Token
}}
"""

PAGES = {
    "Set Card Lists:Magnificent Maestros (TCG-EN)": SET_LIST,
    "Set Card Galleries:Magnificent Maestros (TCG-EN-1E)": SET_GALLERY,
}

MISSING_IMAGES = {"File:UnchainedAbomination-MAMS-EN-StR-1E.png"}
"""Like on the wiki, some Starlight Rares have no image yet."""


class FakeBatcher:
    """Answers the importer's requests right away, from the pages above."""

    def __init__(self, card_pages: list) -> None:
        self.namesToIDs = {name: i for i, name in enumerate(card_pages, 1)}
        self.idsToNames = {i: name for name, i in self.namesToIDs.items()}
        self.idsToNames[0] = "Magnificent Maestros"

    def getPageID(self, page):
        def decorator(callback):
            if page in self.namesToIDs:
                callback(self.namesToIDs[page], page)

        return decorator

    def getPageContents(self, page):
        def decorator(callback):
            if page in PAGES:
                callback(PAGES[page])

        return decorator

    def getImageURL(self, page):
        def decorator(callback):
            if page not in MISSING_IMAGES:
                callback("https://ms.yugipedia.com/" + page[len("File:") :])

        return decorator

    def flushPendingOperations(self):
        pass


def make_card(name: str, card_type: CardType, page_id: int) -> Card:
    return Card(
        id=uuid.uuid4(),
        text={Language.ENGLISH: CardText(name=name)},
        card_type=card_type,
        yugipedia_pages=[ExternalIdPair(name, page_id)],
    )


def import_set():
    card_names = [
        "Blue-Eyes White Dragon, the White Phantom Beast",
        "Unchained Soul Lord of Yama",
        "Unchained Abomination",
        "Kuriboh Token",
    ]
    batcher = FakeBatcher(card_names)
    db = Database()
    for name in card_names:
        card_type = CardType.TOKEN if name.endswith("Token") else CardType.MONSTER
        db.add_card(make_card(name, card_type, batcher.namesToIDs[name]))

    data = wikitextparser.parse(SET_PAGE)
    settable = next(x for x in data.templates if x.name.strip() == "Infobox set")
    set_ = Set(id=uuid.uuid4())
    assert parse_tcg_ocg_set(db, batcher, 0, set_, data, SET_PAGE, settable)

    locale = set_.locales[Locale.ENGLISH]
    art_types = {
        (printing.suffix, printing.rarity): art_type
        for printing, art_type in locale.card_art_types.get(
            SetEdition.FIRST, {}
        ).items()
    }
    images = {
        (printing.suffix, printing.rarity): image
        for printing, image in locale.card_images[SetEdition.FIRST].items()
    }
    printings = [x for content in set_.contents for x in content.cards]
    return art_types, images, printings


def test_set_list_description_gives_extended_art():
    art_types, images, _ = import_set()
    # The gallery marks it
    assert art_types[("125", CardRarity.ULTRA)] == "extended"
    # Only the set list says so
    assert art_types[("124", CardRarity.ULTRA)] == "extended"
    assert art_types[("125", CardRarity.STARLIGHT)] == "extended"
    assert ("124", CardRarity.STARLIGHT) not in images


def test_normal_printing_of_same_card_has_no_art_type():
    art_types, images, _ = import_set()
    assert ("100", CardRarity.ULTRA) in images
    assert ("100", CardRarity.ULTRA) not in art_types


def test_normal_and_extended_rows_with_one_code():
    art_types, images, _ = import_set()
    # The extended art is its own image, so the main one is the normal art
    assert images[("001", CardRarity.ULTRA)].endswith("-UR-1E.png")
    assert ("001", CardRarity.ULTRA) not in art_types
    # Only the extended art row has a Starlight Rare
    assert art_types[("001", CardRarity.STARLIGHT)] == "extended"


def test_description_is_only_kept_for_tokens():
    _, _, printings = import_set()
    assert {x.suffix: x.description for x in printings}["126"] == "art"
    assert all(x.description is None for x in printings if x.suffix != "126")


if __name__ == "__main__":
    for name, test in [*globals().items()]:
        if name.startswith("test_"):
            test()
            print(f"[OK] {name}")
