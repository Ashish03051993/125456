"""A/B experiments — variant assignment + result aggregation.

A single experiment is the landing hero (headline + CTA). Visitors are
assigned to a deterministic variant based on a stable client id (persisted
in localStorage on the frontend). The exposure and any downstream
conversion events are stored in the analytics_events collection with
`properties.variant` — no separate collection needed.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List

VARIANTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "landing_hero": {
        "A": {
            "eyebrow": "Now in private beta — join the waitlist",
            "headline_pre": "Turn a",
            "headline_highlight": "topic",
            "headline_mid": "into a",
            "headline_after": "cinematic video",
            "subtitle": (
                "AI Video Studio writes the script, storyboards every scene, "
                "generates the imagery, records the voiceover and renders a "
                "finished MP4 — then repurposes the same idea into a LinkedIn "
                "post, blog and newsletter."
            ),
            "cta_primary": "Reserve my spot",
            "cta_secondary": "Watch demo",
        },
        "B": {
            "eyebrow": "Ship a week of content in 60 seconds",
            "headline_pre": "One prompt.",
            "headline_highlight": "Four",
            "headline_mid": "polished",
            "headline_after": "content pieces",
            "subtitle": (
                "Type your idea once. Get a cinematic MP4, a LinkedIn post, a "
                "blog article and a newsletter — voiced, subtitled and ready "
                "to publish. Built for creators and marketing teams."
            ),
            "cta_primary": "Get early access",
            "cta_secondary": "See a 30s demo",
        },
    }
}


def assign_variant(experiment: str, client_id: str) -> str:
    """Deterministic assignment based on a hash of client_id + experiment."""
    keys = list(VARIANTS.get(experiment, {}).keys())
    if not keys:
        return "A"
    h = hashlib.sha256(f"{experiment}::{client_id}".encode()).digest()
    idx = h[0] % len(keys)
    return keys[idx]


def variant_content(experiment: str, variant: str) -> Dict[str, str]:
    exp = VARIANTS.get(experiment, {})
    return exp.get(variant) or next(iter(exp.values()), {})


def all_variants(experiment: str) -> List[str]:
    return list(VARIANTS.get(experiment, {}).keys())
