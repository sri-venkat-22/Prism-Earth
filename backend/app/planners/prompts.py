"""Version-controlled Planner prompt, built from the catalog (SRS §14.14).

The Planner's system prompt is assembled *from the active Metadata Catalog* so
it stays in lockstep with the registered fields, presets, and layers — the
catalog is the Planner's only source of domain knowledge (SRS §14.4). Only
selectable (stable/beta) fields are exposed to the model; planned fields are
never listed, so the model cannot even see a field it must not select
(SRS §11.6, §14.10). The anti-hallucination rules (SRS §14.15) and the exact
output schema (SRS §14.13) are stated explicitly.

The prompt is deterministic for a given catalog (fields and presets are emitted
in catalog order), which keeps it cache-friendly (SRS §14.16) and keeps planning
reproducible.
"""

from __future__ import annotations

from app.metadata.catalog import Catalog

# The intent categories the Planner classifies into (SRS §14.7).
INTENT_CATEGORIES: tuple[str, ...] = (
    "Terrain Analysis",
    "Flood Assessment",
    "Wildfire Assessment",
    "Climate Analysis",
    "Land Suitability",
    "Infrastructure Planning",
    "Administrative Lookup",
    "Parcel Information",
    "Renewable Energy Site Selection",
    "Environmental Assessment",
)

_SCHEMA_EXAMPLE = """{
  "intent": "Flood Assessment",
  "presets": ["flood_risk"],
  "fields": ["within_flood_hazard_polygon", "flood_hazard_class", "nearest_waterbody_distance_m"],
  "planning_reason": "Flood assessment requires flood hazard signals and proximity to water."
}"""


def build_planner_system_prompt(catalog: Catalog) -> str:
    """Assemble the Planner system prompt from the catalog (SRS §14.14)."""
    sections = [
        _role_section(),
        _layers_section(catalog),
        _presets_section(catalog),
        _fields_section(catalog),
        _rules_section(),
        _output_section(),
    ]
    return "\n\n".join(sections)


def _role_section() -> str:
    intents = ", ".join(INTENT_CATEGORIES)
    return (
        "You are the Planner for Prism Earth, a deterministic geospatial "
        "intelligence platform for India (pilot region: Telangana).\n"
        "Your ONLY job is to translate a natural-language question about a "
        "location into a structured plan of which registered data fields to "
        "retrieve. You do NOT fetch data, compute values, score suitability, or "
        "write the final answer — other components do that.\n"
        f"Classify the question into one or more of these intents: {intents}. "
        "Report the single best-fitting intent."
    )


def _layers_section(catalog: Catalog) -> str:
    lines = ["The platform organizes fields into these logical layers:"]
    for layer in catalog.layers():
        lines.append(f"- {layer.name} ({layer.id.value}): {layer.purpose}")
    return "\n".join(lines)


def _presets_section(catalog: Catalog) -> str:
    lines = [
        "PRESETS — predefined field bundles. Prefer a preset when it matches the "
        "question; presets expand to a vetted field set (SRS §14.9). Available presets:"
    ]
    for preset in catalog.presets():
        field_list = ", ".join(preset.fields)
        lines.append(f"- {preset.id}: {preset.description}\n    fields: {field_list}")
    return "\n".join(lines)


def _fields_section(catalog: Catalog) -> str:
    lines = [
        "SELECTABLE FIELDS — you may select ONLY field names from this list. "
        "These are every retrievable field, grouped by layer. Any name not "
        "listed here does not exist and must never be used."
    ]
    for layer in catalog.layers():
        layer_fields = [f for f in catalog.fields() if f.layer is layer.id and f.selectable]
        if not layer_fields:
            continue
        lines.append(f"\n[{layer.name}]")
        for field in layer_fields:
            unit = f" [{field.unit}]" if field.unit else ""
            lines.append(f"- {field.name}{unit}: {field.description}")
    return "\n".join(lines)


def _rules_section() -> str:
    return (
        "PLANNING RULES:\n"
        "1. Select the SMALLEST set of fields that answers the question "
        "(SRS §14.8). Do not add unrelated fields.\n"
        "2. Prefer a matching preset; otherwise list individual fields "
        "(SRS §14.9).\n"
        "3. Use ONLY field names from the SELECTABLE FIELDS list and preset ids "
        "from the PRESETS list. Never invent fields, presets, datasets, or "
        "connectors (SRS §14.15).\n"
        "4. If the question cannot be answered with any registered field, return "
        "empty presets and fields and say so in planning_reason (SRS §14.15).\n"
        "5. Do not retrieve data, estimate values, or answer the question — only "
        "plan (SRS §14.12)."
    )


def _output_section() -> str:
    return (
        "OUTPUT — respond with a single JSON object and nothing else, matching "
        "this schema (SRS §14.13):\n"
        f"{_SCHEMA_EXAMPLE}\n"
        "Keys: 'intent' (string), 'presets' (array of preset ids), 'fields' "
        "(array of field names), 'planning_reason' (string). Omit 'layers' and "
        "'connectors' — those are derived downstream."
    )


def build_planner_user_prompt(question: str, *, lat: float, lng: float) -> str:
    """Frame the user's question for the Planner (SRS §14.6)."""
    return (
        f"Location: latitude {lat}, longitude {lng} (India pilot region).\n"
        f"Question: {question}\n\n"
        "Produce the execution plan as JSON."
    )
