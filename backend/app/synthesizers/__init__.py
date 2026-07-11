"""The Synthesizer (SRS §6.5).

Turns the values the Fetch Engine retrieved into a clean prose answer — no
inline citations or source names; sourcing rides in the response payload — and
never fabricates values (SRS §6.5, §16.8, §38.8). Import the public surface here:

    from app.synthesizers import Synthesizer, LLMSynthesizer, TemplateSynthesizer
"""

from __future__ import annotations

from app.synthesizers.synthesizer import (
    LLMSynthesizer,
    SynthesisResult,
    Synthesizer,
    TemplateSynthesizer,
    data_gaps_for,
)

__all__ = [
    "LLMSynthesizer",
    "SynthesisResult",
    "Synthesizer",
    "TemplateSynthesizer",
    "data_gaps_for",
]
