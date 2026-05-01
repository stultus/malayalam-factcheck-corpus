"""Pydantic models for ``configs/malayalam_factcheck_sources.json``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Language = Literal["ml", "en", "multi"]
ExtractorName = Literal["claimreview_jsonld", "css_selectors", "readability_fallback"]
PermissionStatus = Literal["unasked", "requested", "granted", "denied"]


class DiscoveryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitemap: HttpUrl | None = None
    rss: HttpUrl | None = None
    category_pages: list[HttpUrl] = Field(default_factory=list)
    article_url_pattern: str | None = None


class ExtractionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claimreview_jsonld: bool
    selectors: dict[str, str | None] = Field(default_factory=dict)


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    base_url: HttpUrl
    language: Language
    ifcn_signatory: bool = False
    meta_partner: bool | None = None
    publisher_org: str | None = None
    malayalam_section: HttpUrl | None = None
    permission_status: PermissionStatus
    discovery: DiscoveryConfig
    extraction: ExtractionConfig
    user_agent: str | None = None
    notes: str | None = None


class GlobalCrawlerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_agent: str
    default_delay_seconds: int = Field(ge=0)
    respect_robots_txt: bool = True
    max_concurrent_per_host: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    retry_attempts: int = Field(ge=0)


class SourcesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    description: str
    canonical_labels: dict[str, list[str]]
    extraction_priority: list[ExtractorName]
    global_crawler_policy: GlobalCrawlerPolicy
    sources: list[SourceConfig]
    label_ambiguity_notes: list[str] = Field(default_factory=list)
    recommended_negative_class_sourcing: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> SourcesFile:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def source(self, source_id: str) -> SourceConfig:
        for src in self.sources:
            if src.id == source_id:
                return src
        raise KeyError(f"source_id {source_id!r} not found in config")
