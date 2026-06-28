"""Mock identification provider.

Deterministic, offline placeholder so the full pipeline + UI work before any
real AI is wired in. Produces plausible-looking results seeded by the filename
so a given photo always gets the same mock identification.
"""
from __future__ import annotations

import hashlib

from ..models import Identification, IdentifiedSubject

_FAUNA = [
    ("American bison", "Bison are the largest land mammals in North America and can sprint up to 35 mph."),
    ("Elk (wapiti)", "A bull elk's bugle can carry for miles and is one of autumn's signature sounds."),
    ("Grizzly bear", "Grizzlies can smell food from over a mile away thanks to a huge olfactory bulb."),
    ("Gray wolf", "Reintroduced in 1995, wolves reshaped entire ecosystems by changing elk behavior."),
    ("Bald eagle", "A bald eagle's nest can weigh over a ton and be reused for decades."),
    ("Pronghorn", "Pronghorn are the fastest land animal in the Americas, built for endurance running."),
]
_FLORA = [
    ("Lodgepole pine", "Lodgepole pinecones often need fire's heat to release their seeds."),
    ("Indian paintbrush", "This wildflower is partly parasitic, tapping the roots of neighboring plants."),
    ("Quaking aspen", "An aspen grove is often a single organism sharing one vast root system."),
    ("Fireweed", "Fireweed is one of the first plants to colonize burned ground after a wildfire."),
]
_LANDMARK = [
    ("Geyser / hot spring", "Yellowstone sits atop a supervolcano fueling more than 10,000 thermal features."),
    ("Mountain vista", "The Rockies formed over tens of millions of years of tectonic uplift."),
    ("Alpine lake", "High-altitude lakes are often fed by snowmelt and stay cold year-round."),
    ("Waterfall", "Waterfalls form where rivers cross from hard rock to softer, eroding rock."),
]


def _pick(seed: int, table):
    return table[seed % len(table)]


class MockProvider:
    name = "mock"

    def identify(self, image_path: str, context: dict | None = None) -> Identification:
        digest = hashlib.sha1(image_path.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], "big")

        subjects: list[IdentifiedSubject] = []

        # Always a scene/landmark guess.
        l_label, l_fact = _pick(seed, _LANDMARK)
        subjects.append(IdentifiedSubject(
            kind="landmark", label=l_label, confidence=0.55 + (seed % 30) / 100.0,
            fun_fact=l_fact, source="mock"))

        # Alternate between fauna and flora based on the seed.
        if seed % 2 == 0:
            f_label, f_fact = _pick(seed >> 3, _FAUNA)
            subjects.append(IdentifiedSubject(
                kind="fauna", label=f_label, confidence=0.40 + (seed % 40) / 100.0,
                fun_fact=f_fact, source="mock"))
        else:
            f_label, f_fact = _pick(seed >> 3, _FLORA)
            subjects.append(IdentifiedSubject(
                kind="flora", label=f_label, confidence=0.40 + (seed % 40) / 100.0,
                fun_fact=f_fact, source="mock"))

        return Identification(provider=self.name, subjects=subjects)
