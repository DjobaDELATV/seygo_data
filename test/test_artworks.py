#!/usr/bin/env python3
"""Tests linking printings to the artwork of their card they show.

Run with `PYTHONPATH=src python test/test_artworks.py` (or with pytest).
"""
import base64
import uuid

import numpy
from PIL import Image

from ygojson import artworks
from ygojson.database import *


def card_scan(seed: int, edit: float = 0.0) -> Image.Image:
    """A fake card scan whose artwork is random blobs; `edit` covers a corner of it."""
    rng = numpy.random.default_rng(seed)
    art = Image.fromarray(rng.integers(0, 256, (8, 8), dtype=numpy.uint8)).resize(
        (300, 220), Image.BICUBIC
    )
    scan = Image.new("L", (400, 580), 128)
    scan.paste(art, (52, 110))
    if edit:
        scan.paste(200, (52, 110, 52 + int(300 * edit), 110 + int(220 * edit)))
    return scan


class FakeFingerprinter(artworks.Fingerprinter):
    def __init__(self, images: dict) -> None:
        self.cache = {
            artworks._cache_key(url): base64.b64encode(
                artworks.fingerprint(image)
            ).decode()
            for url, image in images.items()
        }


def make_card(*urls: str) -> Card:
    return Card(
        id=uuid.uuid4(),
        card_type=CardType.MONSTER,
        images=[CardImage(id=uuid.uuid4(), card_art=url) for url in urls],
    )


YGOPRODECK = "https://images.ygoprodeck.com/images/cards/1.jpg"
ALT_JP = "https://ms.yugipedia.com/a/aa/Card-LOCR-JP-UR.png"
TCG_EDIT = "https://ms.yugipedia.com/b/bb/Card-RA05-EN-CR-1E.png"


def decide(card: Card, fingerprinter, scans, alternate=False):
    fingerprints = {x.id: fingerprinter.get(x.card_art) for x in card.images}
    groups = artworks._group_artworks(card, fingerprints)
    return artworks.decide(card, scans, alternate, fingerprinter, groups, fingerprints)


def test_similarity():
    a = artworks.fingerprint(card_scan(1))
    assert artworks.similarity(a, a) > 0.99
    assert artworks.similarity(a, artworks.fingerprint(card_scan(2))) < 0.5
    # Scans cropped a bit differently still match
    moved = card_scan(1).crop((4, 4, 400, 580)).resize((400, 580))
    assert artworks.similarity(a, artworks.fingerprint(moved)) > 0.9


def test_printing_gets_its_artwork():
    card = make_card(YGOPRODECK, ALT_JP)
    fp = FakeFingerprinter(
        {
            YGOPRODECK: card_scan(1),
            ALT_JP: card_scan(2),
            "en-normal": card_scan(1),
            "en-alt": card_scan(2),
        }
    )
    assert decide(card, fp, [("en-normal", "tcg")]).image is card.images[0]
    # Like MAMS-EN033: a TCG printing of an artwork whose only scan is OCG
    assert decide(card, fp, [("en-alt", "tcg")]).image is card.images[1]


def test_versions_of_one_artwork_are_told_apart_by_format():
    # Like Dominus Impulse: YGOPRODeck's scan and the censored TCG one look the same
    card = make_card(YGOPRODECK, TCG_EDIT)
    fp = FakeFingerprinter(
        {
            YGOPRODECK: card_scan(1),
            TCG_EDIT: card_scan(1, edit=0.1),
            "en": card_scan(1, edit=0.1),
            "jp": card_scan(1),
        }
    )
    assert (
        len(
            artworks._group_artworks(
                card, {x.id: fp.get(x.card_art) for x in card.images}
            )
        )
        == 1
    )
    assert decide(card, fp, [("en", "tcg")]).image is card.images[1]
    # Nothing says which of the versions is the OCG one
    decision = decide(card, fp, [("jp", "ocg")])
    assert decision.image is None and decision.reason == "no version of its format"


def test_unknown_artwork_gets_nothing():
    card = make_card(YGOPRODECK, ALT_JP)
    fp = FakeFingerprinter(
        {YGOPRODECK: card_scan(1), ALT_JP: card_scan(2), "other": card_scan(3)}
    )
    decision = decide(card, fp, [("other", "tcg")])
    assert decision.image is None and decision.reason == "too close"


def test_scans_that_disagree_get_nothing():
    card = make_card(YGOPRODECK, ALT_JP)
    fp = FakeFingerprinter(
        {
            YGOPRODECK: card_scan(1),
            ALT_JP: card_scan(2),
            "a": card_scan(1),
            "b": card_scan(2),
        }
    )
    decision = decide(card, fp, [("a", "tcg"), ("b", "tcg")])
    assert decision.image is None and decision.reason == "scans disagree"


def test_wiki_alternate_is_never_the_main_artwork():
    card = make_card(YGOPRODECK, ALT_JP)
    fp = FakeFingerprinter(
        {YGOPRODECK: card_scan(1), ALT_JP: card_scan(2), "a": card_scan(1)}
    )
    decision = decide(card, fp, [("a", "tcg")], alternate=True)
    assert decision.image is None and decision.reason == "wiki says alternate"


def test_missing_fingerprint_keeps_nothing():
    card = make_card(YGOPRODECK, ALT_JP)
    fp = FakeFingerprinter({YGOPRODECK: card_scan(1), ALT_JP: card_scan(2)})
    assert decide(card, fp, [("not downloaded", "tcg")]).reason == "no fingerprint"


if __name__ == "__main__":
    for name, test in [*globals().items()]:
        if name.startswith("test_"):
            test()
            print(f"[OK] {name}")
