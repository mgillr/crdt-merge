# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Model card generation with merge provenance metadata for HuggingFace Hub."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crdt_merge.model.provenance import ProvenanceSummary


@dataclass
class ModelCardConfig:
    """Configuration for model card generation.

    Attributes
    ----------
    include_lineage : bool
        Include merge lineage section showing source models (default: True).
    include_strategies : bool
        Include per-layer strategy breakdown (default: True).
    include_crdt_badge : bool
        Include CRDT convergence verification badge (default: True).
    include_eu_ai_act : bool
        Include EU AI Act traceability JSON-LD block (default: False).
    language : str
        Model language tag (default: ``"en"``).
    license : str
        License identifier (default: ``"apache-2.0"``).
    tags : list of str
        Additional tags for the model card.
    """

    include_lineage: bool = True
    include_strategies: bool = True
    include_crdt_badge: bool = True
    include_eu_ai_act: bool = False
    language: str = "en"
    license: str = "apache-2.0"
    tags: List[str] = field(default_factory=list)


class AutoModelCard:
    """Generate HuggingFace model cards with merge provenance metadata.

    Produces markdown model cards that include:
    - Merge lineage DAG (which models contributed)
    - Per-layer strategy decisions
    - CRDT convergence verification status
    - Optional EU AI Act traceability metadata (JSON-LD)

    Parameters
    ----------
    config : ModelCardConfig, optional
        Card generation configuration. Uses defaults if None.
    """

    def __init__(self, config: Optional[ModelCardConfig] = None):
        self.config = config or ModelCardConfig()

    def generate(
        self,
        sources: List[str],
        strategy: str,
        provenance: Optional[ProvenanceSummary] = None,
        weights: Optional[List[float]] = None,
        verified: bool = False,
        base_card: Optional[str] = None,
    ) -> str:
        """Generate a complete model card in markdown format.

        Parameters
        ----------
        sources : list of str
            Source model identifiers (repo IDs or names).
        strategy : str
            Primary merge strategy used.
        provenance : ProvenanceSummary, optional
            Merge provenance data for detailed lineage.
        weights : list of float, optional
            Per-source merge weights.
        verified : bool
            Whether the merge passed CRDT convergence verification.
        base_card : str, optional
            Existing model card to append merge sections to.

        Returns
        -------
        str
            Complete markdown model card.
        """
        sections = []

        # YAML frontmatter
        metadata = self.generate_metadata(sources, strategy, provenance)
        frontmatter = _dict_to_yaml(metadata)
        sections.append(f"---\n{frontmatter}---\n")

        # Title
        sections.append("# Merged Model\n")

        if base_card:
            sections.append(base_card.strip() + "\n")

        # Merge Details section
        if self.config.include_lineage:
            sections.append(self._generate_lineage_section(sources, strategy, weights))

        # Strategy section
        if self.config.include_strategies:
            sections.append(self._generate_strategy_section(strategy, provenance))

        # CRDT Verification section
        if self.config.include_crdt_badge:
            sections.append(self._generate_verification_section(verified))

        # Provenance section
        if provenance is not None:
            sections.append(self._generate_provenance_section(provenance))

        # EU AI Act section
        if self.config.include_eu_ai_act:
            json_ld = self.to_json_ld(sources, strategy, provenance)
            sections.append(self._generate_eu_ai_act_section(json_ld))

        return "\n".join(sections)

    def generate_metadata(
        self,
        sources: List[str],
        strategy: str,
        provenance: Optional[ProvenanceSummary] = None,
    ) -> dict:
        """Generate YAML frontmatter metadata dictionary.

        Parameters
        ----------
        sources : list of str
            Source model identifiers.
        strategy : str
            Primary merge strategy.
        provenance : ProvenanceSummary, optional
            Merge provenance data.

        Returns
        -------
        dict
            Metadata suitable for HuggingFace model card YAML frontmatter.
        """
        tags = ["merge", "crdt-merge", f"merge-strategy-{strategy}"]
        tags.extend(self.config.tags)

        metadata: Dict[str, Any] = {
            "library_name": "crdt-merge",
            "tags": tags,
            "license": self.config.license,
            "language": self.config.language,
        }

        # Merge-specific metadata
        merge_meta: Dict[str, Any] = {
            "strategy": strategy,
            "sources": sources,
        }

        if provenance is not None:
            merge_meta["overall_conflict"] = round(provenance.overall_conflict, 4)
            merge_meta["dominant_model"] = provenance.dominant_model

        metadata["merge_details"] = merge_meta
        return metadata

    def to_json_ld(
        self,
        sources: List[str],
        strategy: str,
        provenance: Optional[ProvenanceSummary] = None,
    ) -> dict:
        """Generate JSON-LD metadata for EU AI Act traceability.

        Parameters
        ----------
        sources : list of str
            Source model identifiers.
        strategy : str
            Primary merge strategy.
        provenance : ProvenanceSummary, optional
            Merge provenance data.

        Returns
        -------
        dict
            JSON-LD structured metadata for regulatory compliance.
        """
        json_ld: Dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "Merged Model",
            "applicationCategory": "Machine Learning Model",
            "creator": {
                "@type": "SoftwareApplication",
                "name": "crdt-merge",
                "url": "https://github.com/mgillr/crdt-merge",
            },
            "isBasedOn": [
                {"@type": "SoftwareApplication", "name": src} for src in sources
            ],
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "merge_strategy",
                    "value": strategy,
                },
                {
                    "@type": "PropertyValue",
                    "name": "num_sources",
                    "value": len(sources),
                },
            ],
        }

        if provenance is not None:
            json_ld["additionalProperty"].extend([
                {
                    "@type": "PropertyValue",
                    "name": "overall_conflict_score",
                    "value": round(provenance.overall_conflict, 4),
                },
                {
                    "@type": "PropertyValue",
                    "name": "dominant_model_index",
                    "value": provenance.dominant_model,
                },
            ])

        return json_ld

    # ---- Private section generators ----

    def _generate_lineage_section(
        self, sources: List[str], strategy: str, weights: Optional[List[float]]
    ) -> str:
        lines = ["## Merge Details\n"]
        lines.append(f"This model was created by merging {len(sources)} source models ")
        lines.append(f"using the **{strategy}** strategy.\n")
        lines.append("| # | Source Model | Weight |")
        lines.append("|---|-------------|--------|")
        for i, src in enumerate(sources):
            w = weights[i] if weights and i < len(weights) else "equal"
            lines.append(f"| {i + 1} | `{src}` | {w} |")
        lines.append("")
        return "\n".join(lines)

    def _generate_strategy_section(
        self, strategy: str, provenance: Optional[ProvenanceSummary]
    ) -> str:
        lines = ["## Strategy\n"]
        lines.append(f"- **Primary strategy:** `{strategy}`")

        if provenance is not None and provenance.per_layer:
            lines.append(f"- **Layers merged:** {len(provenance.per_layer)}")
            # Per-layer breakdown
            strategy_counts: Dict[str, int] = {}
            for layer_info in provenance.per_layer.values():
                s = getattr(layer_info, "strategy_used", strategy)
                strategy_counts[s] = strategy_counts.get(s, 0) + 1
            if strategy_counts:
                lines.append("\n**Strategy distribution:**\n")
                lines.append("| Strategy | Layers |")
                lines.append("|----------|--------|")
                for s_name, count in sorted(strategy_counts.items()):
                    lines.append(f"| `{s_name}` | {count} |")
        lines.append("")
        return "\n".join(lines)

    def _generate_verification_section(self, verified: bool) -> str:
        lines = ["## CRDT Verification\n"]
        if verified:
            badge = "![CRDT Verified](https://img.shields.io/badge/CRDT-verified-brightgreen)"
            lines.append(f"{badge}\n")
            lines.append("This merge has been verified for CRDT convergence properties.")
        else:
            badge = "![CRDT Unverified](https://img.shields.io/badge/CRDT-unverified-yellow)"
            lines.append(f"{badge}\n")
            lines.append("This merge has not been verified for CRDT convergence properties.")
        lines.append("")
        return "\n".join(lines)

    def _generate_provenance_section(self, provenance: ProvenanceSummary) -> str:
        lines = ["## Provenance\n"]
        lines.append(f"- **Overall conflict score:** {provenance.overall_conflict:.4f}")
        lines.append(f"- **Dominant model index:** {provenance.dominant_model}")

        if provenance.layer_conflict_ranking:
            lines.append(f"- **Highest-conflict layers:** "
                         f"{', '.join(f'`{l}`' for l in provenance.layer_conflict_ranking[:5])}")

        if provenance.per_layer:
            lines.append("\n<details>")
            lines.append("<summary>Per-layer conflict scores</summary>\n")
            lines.append("| Layer | Strategy | Conflict Score | Dominant Source |")
            lines.append("|-------|----------|---------------|-----------------|")
            for name, lp in provenance.per_layer.items():
                s = getattr(lp, "strategy_used", "N/A")
                cs = getattr(lp, "conflict_score", 0.0)
                ds = getattr(lp, "dominant_source", "N/A")
                lines.append(f"| `{name}` | `{s}` | {cs:.4f} | {ds} |")
            lines.append("\n</details>")
        lines.append("")
        return "\n".join(lines)

    def _generate_eu_ai_act_section(self, json_ld: dict) -> str:
        lines = ["## EU AI Act Traceability\n"]
        lines.append("The following JSON-LD metadata provides traceability ")
        lines.append("information for regulatory compliance.\n")
        lines.append("```json")
        lines.append(json.dumps(json_ld, indent=2))
        lines.append("```")
        lines.append("")
        return "\n".join(lines)


def _dict_to_yaml(d: dict, indent: int = 0) -> str:
    """Minimal YAML serializer for metadata frontmatter (no PyYAML dependency)."""
    lines = []
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dict_to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # Inline dict items not supported; skip for simplicity
                    lines.append(f"{prefix}  - {json.dumps(item)}")
                else:
                    lines.append(f"{prefix}  - {item}")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{prefix}{key}: {value}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines) + "\n"
