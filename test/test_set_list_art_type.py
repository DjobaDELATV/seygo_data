#!/usr/bin/env python3
"""Test that a set list row's description gives the art type of its printings.

Magnificent Maestros prints Unchained Soul Lord of Yama twice: MAMS-EN100 with its
normal art, and MAMS-EN125 with extended art. Only the set list says EN124 and the
Starlight Rare of EN125 are extended arts: their galleries and files don't. The German
list doesn't say so either.

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
| lists        = EN, DE
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
MAMS-EN127; Dark Magician; Ultra Rare; New artwork // description::(stamp artwork)
MAMS-EN128; Skull Servant; Ultra Rare
MAMS-EN128; Skull Servant; Ultra Rare; New artwork // description::(chibi artwork)
MAMS-EN129; Effect Veiler; Ultra Rare; New artwork // description::(new artwork)
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

# Like some locales' lists, it doesn't have the descriptions
DE_SET_LIST = """{{Set page header}}

{{Set list|region=DE|rarities=Ultra Rare|print=Reprint|
MAMS-DE001; Blue-Eyes White Dragon, the White Phantom Beast;; New
MAMS-DE001; Blue-Eyes White Dragon, the White Phantom Beast; Ultra Rare, Starlight Rare; New
MAMS-DE100; Unchained Soul Lord of Yama
MAMS-DE124; Unchained Abomination; Ultra Rare, Starlight Rare; New artwork
MAMS-DE125; Unchained Soul Lord of Yama; Ultra Rare, Starlight Rare; New artwork
MAMS-DE126; Kuriboh Token; Common; New // description::(art)
}}
"""

PAGES = {
    "Set Card Lists:Magnificent Maestros (TCG-EN)": SET_LIST,
    "Set Card Lists:Magnificent Maestros (TCG-DE)": DE_SET_LIST,
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
        "Dark Magician",
        "Skull Servant",
        "Effect Veiler",
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


def test_printings_have_the_arts_of_their_rows():
    _, _, printings = import_set()
    arts = {(x.suffix, x.rarity): (x.art_type, x.variants) for x in printings}
    # A normal and an extended art row: the extended art is another art of the printing
    assert arts[("001", CardRarity.ULTRA)] == (
        None,
        [{"artType": "extended", "label": "EA"}],
    )
    # Only an extended art row: the printing is an extended art, image or not
    assert arts[("001", CardRarity.STARLIGHT)] == ("extended", [])
    assert arts[("124", CardRarity.STARLIGHT)] == ("extended", [])
    assert arts[("100", CardRarity.ULTRA)] == (None, [])
    # A list without the descriptions doesn't make them normal arts
    assert arts[("125", CardRarity.ULTRA)] == ("extended", [])
    # Tokens' descriptions tell them apart, not their art
    assert arts[("126", CardRarity.COMMON)] == (None, [])


def test_printing_arts_are_in_the_json():
    _, _, printings = import_set()
    by_key = {(x.suffix, x.rarity): x._to_json() for x in printings}
    assert by_key[("001", CardRarity.ULTRA)]["variants"] == [
        {"artType": "extended", "label": "EA"}
    ]
    assert by_key[("001", CardRarity.STARLIGHT)]["artType"] == "extended"
    assert "artType" not in by_key[("100", CardRarity.ULTRA)]
    assert "variants" not in by_key[("100", CardRarity.ULTRA)]


def test_set_list_names_its_alternate_arts():
    _, _, printings = import_set()
    by_key = {(x.suffix, x.rarity): x for x in printings}
    # Stores tell stamp and chibi arts apart from other alternate arts
    stamp = by_key[("127", CardRarity.ULTRA)]
    assert (stamp.art_type, stamp.art_label, stamp.variants) == (
        "alternate",
        "Stamp",
        [],
    )
    assert stamp._to_json()["artLabel"] == "Stamp"
    assert by_key[("128", CardRarity.ULTRA)].variants == [
        {"artType": "alternate", "label": "Chibi"}
    ]
    # A new artwork is just an alternate art
    new = by_key[("129", CardRarity.ULTRA)]
    assert (new.art_type, new.art_label) == ("alternate", None)
    assert "artLabel" not in new._to_json()


if __name__ == "__main__":
    for name, test in [*globals().items()]:
        if name.startswith("test_"):
            test()
            print(f"[OK] {name}")
