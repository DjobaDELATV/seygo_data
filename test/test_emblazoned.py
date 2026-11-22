#!/usr/bin/env python3
"""Test that emblazoned cards get their own printings and rarities.

Limited Pack World Championship 2026 prints each card as an Ultra and a Secret Rare,
with and without the World Championship logo in its text box. Its set list only has
the ones without, but its gallery has sections of emblazoned ones. Its alternate arts
and "Monster Reborn" are only emblazoned, though the set list doesn't say so.

Run with `PYTHONPATH=src python test/test_emblazoned.py` (or with pytest).
"""
import uuid

import wikitextparser

from ygojson.database import *
from ygojson.importers.yugipedia import parse_tcg_ocg_set

SET_NAME = "Limited Pack World Championship 2026"

SET_PAGE = """{{Infobox set
| en_name         = Limited Pack World Championship 2026
| en_release_date = August 29, 2026
}}

== Lists ==
{{Set navigation
| lists        = EN
| 1e_galleries = EN
}}
"""

SET_LIST = """{{Set page header}}

{{Set list|region=EN|rarities=Ultra Rare, Secret Rare|print=Reprint|
26LP-EN001; Monster Reborn; Secret Rare, Starlight Rare; New artwork
26LP-EN002; Dracotail Faimena
26LP-EN002; Dracotail Faimena; Secret Rare; New artwork // description::(alternate artwork)
26LP-EN013; Lunalight Masquerade
}}
"""

SET_GALLERY = """{{Set page header}}

== Ultra Rares ==
{{Set gallery|rarity=Ultra Rare|
26LP-EN002; Dracotail Faimena
26LP-EN013; Lunalight Masquerade
}}

== Secret Rares ==
{{Set gallery|rarity=Secret Rare|
26LP-EN002; Dracotail Faimena
26LP-EN013; Lunalight Masquerade
}}

== Emblazoned Ultra Rares ==
{{Set gallery|rarity=Ultra Rare|alt=Emblazoned|
26LP-EN002; Dracotail Faimena
26LP-EN013; Lunalight Masquerade
}}

== Emblazoned Secret Rares ==
{{Set gallery|rarity=Secret Rare|alt=Emblazoned|
26LP-EN001; Monster Reborn
26LP-EN002; Dracotail Faimena
26LP-EN002; Dracotail Faimena;; AA // description::(alternate artwork)
26LP-EN013; Lunalight Masquerade
}}

== Emblazoned Starlight Rare ==
{{Set gallery|rarity=Starlight Rare|alt=Emblazoned|
26LP-EN001; Monster Reborn
}}
"""

PAGES = {
    f"Set Card Lists:{SET_NAME} (TCG-EN)": SET_LIST,
    f"Set Card Galleries:{SET_NAME} (TCG-EN-1E)": SET_GALLERY,
}

MISSING_IMAGES = {"File:LunalightMasquerade-26LP-EN-ScR-1E-Emblazoned.png"}
"""Like on the wiki, some emblazoned cards have no image yet."""

CARD_NAMES = ["Monster Reborn", "Dracotail Faimena", "Lunalight Masquerade"]


class FakeBatcher:
    """Answers the importer's requests right away, from the pages above."""

    def __init__(self, card_pages: list) -> None:
        self.namesToIDs = {name: i for i, name in enumerate(card_pages, 1)}
        self.idsToNames = {i: name for name, i in self.namesToIDs.items()}
        self.idsToNames[0] = SET_NAME

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


def make_db(batcher: FakeBatcher) -> Database:
    db = Database()
    for name in CARD_NAMES:
        db.add_card(
            Card(
                id=uuid.uuid4(),
                text={Language.ENGLISH: CardText(name=name)},
                card_type=CardType.MONSTER,
                yugipedia_pages=[ExternalIdPair(name, batcher.namesToIDs[name])],
            )
        )
    return db


def import_set(set_: Set = None, db: Database = None):
    batcher = FakeBatcher(CARD_NAMES)
    db = db or make_db(batcher)
    data = wikitextparser.parse(SET_PAGE)
    settable = next(x for x in data.templates if x.name.strip() == "Infobox set")
    set_ = set_ or Set(id=uuid.uuid4())
    assert parse_tcg_ocg_set(db, batcher, 0, set_, data, SET_PAGE, settable)
    return set_


def printings_of(set_: Set):
    return {(x.suffix, x.rarity): x for content in set_.contents for x in content.cards}


def test_emblazoned_printings_are_made_from_the_gallery():
    printings = printings_of(import_set())
    assert set(printings) == {
        ("001", CardRarity.SECRET_EMBLAZONED),
        ("001", CardRarity.STARLIGHT_EMBLAZONED),
        ("002", CardRarity.ULTRA),
        ("002", CardRarity.SECRET),
        ("002", CardRarity.ULTRA_EMBLAZONED),
        ("002", CardRarity.SECRET_EMBLAZONED),
        ("013", CardRarity.ULTRA),
        ("013", CardRarity.SECRET),
        ("013", CardRarity.ULTRA_EMBLAZONED),
        # Even without an image
        ("013", CardRarity.SECRET_EMBLAZONED),
    }


def test_emblazoned_images_are_not_variants():
    set_ = import_set()
    locale = set_.locales[Locale.ENGLISH]
    images = {
        (p.suffix, p.rarity): image
        for p, image in locale.card_images[SetEdition.FIRST].items()
    }
    variants = {
        (p.suffix, p.rarity): v
        for p, v in locale.card_variants.get(SetEdition.FIRST, {}).items()
    }
    assert images[("002", CardRarity.SECRET)].endswith("-ScR-1E.png")
    assert ("002", CardRarity.SECRET) not in variants
    assert images[("002", CardRarity.ULTRA_EMBLAZONED)].endswith(
        "-UR-1E-Emblazoned.png"
    )
    # The alternate art is in the emblazoned section, so it's an emblazoned one
    assert images[("002", CardRarity.SECRET_EMBLAZONED)].endswith(
        "-ScR-1E-Emblazoned.png"
    )
    assert [
        (x["label"], x["artType"])
        for x in variants[("002", CardRarity.SECRET_EMBLAZONED)]
    ] == [("AA", "alternate")]
    assert not any(x["label"] == "Emblazoned" for v in variants.values() for x in v)


def test_printings_keep_their_ids():
    db = make_db(FakeBatcher(CARD_NAMES))
    set_ = import_set(db=db)
    old = printings_of(set_)
    # Like the export before emblazoned rarities: "Monster Reborn" was a Secret Rare
    old_reborn = old[("001", CardRarity.SECRET_EMBLAZONED)]
    old_reborn.rarity = CardRarity.SECRET
    printings = printings_of(import_set(set_, db))
    assert printings[("001", CardRarity.SECRET_EMBLAZONED)].id == old_reborn.id
    for key in [("002", CardRarity.ULTRA), ("002", CardRarity.ULTRA_EMBLAZONED)]:
        assert printings[key].id == old[key].id


def test_list_alternate_art_goes_to_the_emblazoned_printing():
    printings = printings_of(import_set())
    # The set list puts the alternate art on the Secret Rare, but the gallery shows it
    # on the emblazoned one
    assert printings[("002", CardRarity.SECRET)].variants == []
    emblazoned = printings[("002", CardRarity.SECRET_EMBLAZONED)]
    assert emblazoned.art_type is None
    assert emblazoned.variants == [{"artType": "alternate", "label": "AA"}]
    # Nothing says the others have another art
    assert printings[("013", CardRarity.SECRET_EMBLAZONED)].variants == []


if __name__ == "__main__":
    for name, test in [*globals().items()]:
        if name.startswith("test_"):
            test()
            print(f"[OK] {name}")
