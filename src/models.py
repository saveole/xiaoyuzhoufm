from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


@dataclass
class EpisodeMeta:
    title: str
    podcast: str = ""
    hosts: list[str] = field(default_factory=list)
    guests: list[str] = field(default_factory=list)
    published_at: str = ""
    duration: float = 0.0
    shownotes: str = ""
    source_url: str = ""
