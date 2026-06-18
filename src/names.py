import re
from typing import Optional

from models import Segment, EpisodeMeta


def extract_candidates(meta: EpisodeMeta) -> list[str]:
    candidates = []
    candidates.extend(meta.hosts)
    candidates.extend(meta.guests)

    if meta.shownotes:
        mentions = re.findall(
            r'[@＠]([\u4e00-\u9fa5\w·]{2,8})',
            meta.shownotes,
        )
        for m in mentions:
            if m not in candidates:
                candidates.append(m)

    return candidates


def guess_speaker_names(
    segments: list[Segment],
    meta: EpisodeMeta,
    speaker_map: Optional[dict[str, str]] = None,
) -> list[Segment]:
    if speaker_map is None:
        speaker_map = {}

    for seg in segments:
        if seg.speaker and seg.speaker in speaker_map:
            seg.speaker = speaker_map[seg.speaker]

    return segments
