"""Links printings to the artwork of their card they show, by comparing images.

Yugipedia says what artworks a card has, but not which printings show which artwork. So for
cards with many artworks, each printing's scan is compared to the scan given for each artwork,
and the printing's ``imageID`` is set to the artwork it looks like.

Artworks that look the same, like the OCG artwork of a card and its censored TCG one, can't be
told apart by their images: the printing gets the one of its format, or none.
"""

import base64
import concurrent.futures
import datetime
import gzip
import io
import json
import logging
import os.path
import re
import time
import typing
import uuid

import numpy
import requests
import tqdm
from PIL import Image, ImageFilter

from .database import *

FINGERPRINTS_FILENAME = "artwork_fingerprints.json.gz"
FINGERPRINTS_VERSION = 1

SIZE = 32
"""The width and height of the part of a fingerprint that's compared."""
SHIFT = 2
"""How many pixels a fingerprint can be moved by, so scans cropped a bit differently match."""

SAME_ARTWORK = 0.85
"""Artworks whose images are at least this similar are the same, like censored versions."""
MIN_SIMILARITY = 0.6
"""A scan less similar than this to all artworks shows none of them."""
MIN_MARGIN = 0.1
"""How much more a scan must look like its artwork than like any other."""

ART_BOX = (0.13, 0.19, 0.87, 0.70)
PENDULUM_ART_BOX = (0.10, 0.19, 0.90, 0.50)
"""Where the artwork is on a card, as fractions of its width and height."""

OCG_LOCALES = {
    Locale.JAPANESE,
    Locale.ASIAN_ENGLISH,
    Locale.KOREAN,
    Locale.CHINESE_SIMPLIFIED,
    Locale.CHINESE_TRADITIONAL,
}
OCG_FILE_RE = re.compile(r"-(?:JP|JA|AE|KR|SC|TC)-")
TCG_FILE_RE = re.compile(r"-(?:EN|NA|EU|OC|FR|FC|DE|IT|PT|SP)-")


def _cache_key(url: str) -> str:
    # Yugipedia serves the same file from more than one host
    match = re.match(r"https?://(?:img|ms)\.yugipedia\.com/+(.*)", url)
    return "yugipedia:" + match.group(1) if match else url


def load_fingerprints() -> typing.Dict[str, str]:
    path = os.path.join(TEMP_DIR, FINGERPRINTS_FILENAME)
    if not os.path.exists(path):
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as file:
        data = json.load(file)
    if data.get("version") != FINGERPRINTS_VERSION:
        return {}
    return data["fingerprints"]


def save_fingerprints(fingerprints: typing.Dict[str, str]) -> None:
    os.makedirs(TEMP_DIR, exist_ok=True)
    path = os.path.join(TEMP_DIR, FINGERPRINTS_FILENAME)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        json.dump({"version": FINGERPRINTS_VERSION, "fingerprints": fingerprints}, file)


def fingerprint(image: Image.Image, pendulum: bool = False) -> bytes:
    """Gets a blurred, grayscale thumbnail of a card's artwork."""
    w, h = image.size
    box = PENDULUM_ART_BOX if pendulum else ART_BOX
    art = image.convert("L").crop(
        (int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3]))
    )
    side = SIZE + 2 * SHIFT
    art = art.resize((side, side), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    return art.tobytes()


def similarity(a: bytes, b: bytes) -> float:
    """Gets how alike two fingerprints are, from -1 to 1, allowing them to be moved a bit."""
    side = SIZE + 2 * SHIFT
    x = numpy.frombuffer(a, dtype=numpy.uint8).reshape(side, side).astype(float)
    y = numpy.frombuffer(b, dtype=numpy.uint8).reshape(side, side).astype(float)
    center = x[SHIFT : SHIFT + SIZE, SHIFT : SHIFT + SIZE]
    center = center - center.mean()
    center /= numpy.linalg.norm(center) or 1
    best = -1.0
    for dy in range(2 * SHIFT + 1):
        for dx in range(2 * SHIFT + 1):
            other = y[dy : dy + SIZE, dx : dx + SIZE]
            other = other - other.mean()
            best = max(
                best, float((center * other).sum()) / (numpy.linalg.norm(other) or 1)
            )
    return best


class Fingerprinter:
    """Gets the fingerprints of images, from the cache or by downloading at most `budget` of them."""

    def __init__(self, budget: int) -> None:
        self.cache = load_fingerprints()
        self.budget = budget
        self.n_downloaded = 0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def get(self, url: str) -> typing.Optional[bytes]:
        """Gets a fingerprint from the cache. An empty one means the image couldn't be read."""
        value = self.cache.get(_cache_key(url))
        return None if value is None else base64.b64decode(value)

    def fetch(self, urls: typing.Dict[str, bool]) -> None:
        """Downloads the images not in the cache, given whether they're Pendulum cards."""
        todo = [(u, p) for u, p in urls.items() if _cache_key(u) not in self.cache]
        todo = todo[: max(0, self.budget - self.n_downloaded)]
        if not todo:
            return

        def download(
            url: str, pendulum: bool
        ) -> typing.Tuple[str, typing.Optional[str]]:
            """Gets an image's fingerprint, "" if it's gone or unreadable,
            or None if it's worth trying again next run."""
            for attempt in range(2):
                try:
                    response = self.session.get(url, timeout=60)
                    if response.status_code in (404, 410):
                        logging.warning(f"Could not fingerprint {url}: it's gone")
                        return url, ""
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    if attempt:
                        logging.warning(f"Could not fingerprint {url}: {e}")
                        return url, None
                    time.sleep(5)
            try:
                with Image.open(io.BytesIO(response.content)) as image:
                    return url, base64.b64encode(fingerprint(image, pendulum)).decode()
            except OSError as e:
                logging.warning(f"Could not fingerprint {url}: {e}")
                return url, ""

        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            for url, value in tqdm.tqdm(
                pool.map(lambda x: download(*x), todo),
                total=len(todo),
                desc="Fingerprinting artworks",
            ):
                if value is not None:
                    self.cache[_cache_key(url)] = value
        self.n_downloaded += len(todo)

    def save(self) -> None:
        save_fingerprints(self.cache)


def _image_format(image: CardImage) -> typing.Optional[str]:
    """Gets the format the scan of an artwork is from, if its file name says it.
    YGOPRODeck's scans may be of either: Slate Warrior's has the OCG artwork.
    """
    url = image.card_art or ""
    if "yugipedia.com" not in url:
        return None
    if OCG_FILE_RE.search(url):
        return "ocg"
    if TCG_FILE_RE.search(url):
        return "tcg"
    return None


def _group_artworks(
    card: Card, fingerprints: typing.Dict[uuid.UUID, bytes]
) -> typing.List[typing.List[CardImage]]:
    """Groups a card's artworks that look the same, in the order of the card's images."""
    groups: typing.List[typing.List[CardImage]] = []
    for image in card.images:
        fp = fingerprints.get(image.id)
        if not fp:
            continue
        for group in groups:
            if similarity(fp, fingerprints[group[0].id]) >= SAME_ARTWORK:
                group.append(image)
                break
        else:
            groups.append([image])
    return groups


class Decision(typing.NamedTuple):
    image: typing.Optional[CardImage]
    reason: str
    scores: typing.List[typing.Tuple[str, float, float]]
    """For each scan: its URL, its best similarity and its margin over the next artwork."""


def decide(
    card: Card,
    scans: typing.List[typing.Tuple[str, str]],
    alternate: bool,
    fingerprinter: Fingerprinter,
    groups: typing.List[typing.List[CardImage]],
    fingerprints: typing.Dict[uuid.UUID, bytes],
) -> Decision:
    """Finds the artwork a printing shows, given its scans and their formats."""
    voted: typing.Set[int] = set()
    formats: typing.Set[str] = set()
    voters: typing.List[bytes] = []
    scores = []
    for url, fmt in scans:
        fp = fingerprinter.get(url)
        if not fp:
            continue
        sims = sorted(
            (
                (max(similarity(fp, fingerprints[x.id]) for x in group), i)
                for i, group in enumerate(groups)
            ),
            reverse=True,
        )
        best, group = sims[0]
        margin = best - sims[1][0] if len(sims) > 1 else 1.0
        scores.append((url, round(best, 3), round(margin, 3)))
        if best >= MIN_SIMILARITY and margin >= MIN_MARGIN:
            voted.add(group)
            formats.add(fmt)
            voters.append(fp)
    if not scores:
        return Decision(None, "no fingerprint", scores)
    if not voted:
        return Decision(None, "too close", scores)
    if len(voted) > 1:
        return Decision(None, "scans disagree", scores)
    group = groups[voted.pop()]
    # The wiki says it's an alternate artwork, so it can't be the card's main one
    if alternate and card.images[0] in group:
        return Decision(None, "wiki says alternate", scores)
    if len(group) == 1:
        return Decision(group[0], "artwork", scores)
    # The same artwork in many versions, like a censored one: only the format tells them apart
    if len(formats) == 1:
        fmt = formats.pop()
        versions = [x for x in group if _image_format(x) == fmt]
        if versions:
            image = max(
                versions,
                key=lambda x: sum(similarity(v, fingerprints[x.id]) for v in voters),
            )
            return Decision(image, "artwork version of its format", scores)
    return Decision(None, "no version of its format", scores)


def _printing_scans(
    db: Database,
) -> typing.Tuple[
    typing.Dict[CardPrinting, typing.List[typing.Tuple[str, str, datetime.date]]],
    typing.Set[CardPrinting],
]:
    """Gets the scans of each printing, with their format and the date of their set,
    and the printings the wiki says are alternate artworks.
    """
    result: typing.Dict[
        CardPrinting, typing.List[typing.Tuple[str, str, datetime.date]]
    ] = {}
    alternates: typing.Set[CardPrinting] = set()
    for set_ in db.sets:
        for locale in set_.locales.values():
            fmt = "ocg" if locale.key in OCG_LOCALES else "tcg"
            date = locale.date or set_.date or datetime.date.min
            for images in locale.card_images.values():
                for printing, url in images.items():
                    scans = result.setdefault(printing, [])
                    if url not in (x[0] for x in scans):
                        scans.append((url, fmt, date))
            for art_types in locale.card_art_types.values():
                for printing, art_type in art_types.items():
                    if art_type == "alternate":
                        alternates.add(printing)
    return result, alternates


def link_printings_to_artworks(
    db: Database, download_budget: int
) -> typing.Dict[str, int]:
    """Sets the ``imageID`` of printings of cards with many artworks.

    At most `download_budget` images are downloaded; the others wait for the next run.
    Returns how many printings each reason was given for.
    """
    fingerprinter = Fingerprinter(download_budget)
    all_scans, alternates = _printing_scans(db)
    by_card: typing.Dict[Card, typing.List[CardPrinting]] = {}
    for printing in all_scans:
        if len(printing.card.images) >= 2:
            by_card.setdefault(printing.card, []).append(printing)

    def is_pendulum(card: Card) -> bool:
        return MonsterCardType.PENDULUM in (card.monster_card_types or [])

    # The newest printings are fingerprinted first
    def newest(card: Card) -> datetime.date:
        return max(x[2] for p in by_card[card] for x in all_scans[p])

    cards = sorted(by_card, key=newest, reverse=True)
    # A card's artworks and printings are fetched together, so each run finishes whole cards
    urls: typing.Dict[str, bool] = {}
    for card in cards:
        for image in card.images:
            if image.card_art:
                urls.setdefault(image.card_art, is_pendulum(card))
        for printing in by_card[card]:
            for url, _, _ in all_scans[printing]:
                urls.setdefault(url, is_pendulum(card))
    fingerprinter.fetch(urls)
    fingerprinter.save()

    counts: typing.Dict[str, int] = {}
    for card in tqdm.tqdm(cards, desc="Linking printings to artworks"):
        fingerprints = {
            x.id: fingerprinter.get(x.card_art) for x in card.images if x.card_art
        }
        fingerprints = {k: v for k, v in fingerprints.items() if v}
        groups = _group_artworks(card, fingerprints)
        for printing in by_card[card]:
            if printing.image and printing.image not in card.images:
                printing.image = None
            if len(groups) < 1:
                reason = "no artwork fingerprint"
            else:
                decision = decide(
                    card,
                    [(url, fmt) for url, fmt, _ in all_scans[printing]],
                    printing in alternates,
                    fingerprinter,
                    groups,
                    fingerprints,
                )
                reason = decision.reason
                if decision.image:
                    printing.image = decision.image
                elif decision.reason != "no fingerprint":
                    printing.image = None
            counts[reason] = counts.get(reason, 0) + 1
    return counts
