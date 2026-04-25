"""Canonical record for one fact-check article.

Redistribution note: ``evidence_text`` holds the publisher's full debunking
prose and is the highest-risk field in any public release. The packaging
stage must excerpt or strip it for publishable corpus tiers. See LEGAL.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

ClaimScript = Literal["mlym", "latn", "mixed", "unknown"]
Language = Literal["ml", "en", "multi"]
VerdictCanonical = Literal[
    "false", "misleading", "partly_false", "true", "unverified", "satire", "unknown"
]
LabelSource = Literal["ifcn", "media_house", "government", "weakly_labelled"]
ExtractorUsed = Literal["claimreview_jsonld", "css_selectors", "readability"]


class FactCheckRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    source_id: str
    url: HttpUrl
    url_canonical: HttpUrl | None = None

    claim_text: str
    claim_text_script: ClaimScript
    evidence_text: str
    title: str
    language: Language

    verdict_raw: str
    verdict_canonical: VerdictCanonical
    label_source: LabelSource

    published_date: datetime
    crawled_date: datetime
    extractor_used: ExtractorUsed
    extractor_confidence: float = Field(ge=0.0, le=1.0)

    claim_embedding_hash: str | None = None
    duplicate_of: str | None = None
