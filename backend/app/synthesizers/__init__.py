"""The Synthesizer (SRS §6.5).

Turns the values the Fetch Engine retrieved into a cited, human-readable answer,
marking unavailable data explicitly and never fabricating values (SRS §6.5,
§16.8, §38.8). Import the public surface here:

    from app.synthesizers import Synthesizer, LLMSynthesizer, TemplateSynthesizer
"""

from __future__ import annotations

from app.synthesizers.synthesizer import (
    LLMSynthesizer,
    SynthesisResult,
    Synthesizer,
    TemplateSynthesizer,
)

__all__ = [
    "LLMSynthesizer",
    "SynthesisResult",
    "Synthesizer",
    "TemplateSynthesizer",
]
