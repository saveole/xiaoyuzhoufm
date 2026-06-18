import json
import os
import time
from typing import Optional

from config import HF_TOKEN
from models import Segment


def diarize_audio(
    audio_path: str,
    segments: list[Segment],
    hf_token: Optional[str] = None,
    cache_dir: str = "audio_files",
) -> list[Segment]:
    token = hf_token or HF_TOKEN
    if not token:
        raise ValueError(
            "HF_TOKEN 未设置。请设置环境变量 HF_TOKEN 或 "
            "在 .env 文件中配置 HF_TOKEN=your_token"
        )

    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    cache_path = os.path.join(cache_dir, f"{base_name}.diarization.json")

    if os.path.exists(cache_path):
        print("加载缓存的 diarization 结果...")
        with open(cache_path, "r", encoding="utf-8") as f:
            diarization_data = json.load(f)
        speaker_turns = diarization_data
    else:
        speaker_turns = _run_pyannote(audio_path, token)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(speaker_turns, f, ensure_ascii=False)

    return _assign_speakers(segments, speaker_turns)


def _run_pyannote(audio_path: str, hf_token: str) -> list[dict]:
    print("加载 pyannote/speaker-diarization-3.1...")
    start_time = time.time()

    try:
        from pyannote.audio import Pipeline
    except ImportError:
        raise ImportError(
            "pyannote.audio 未安装。请运行：pip install pyannote.audio torchaudio"
        )

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )

    if HF_TOKEN:
        device = next(pipeline.parameters()).device
        print(f"Pyannote 运行设备: {device}")

    print("开始说话人区分...")
    diarization = pipeline(audio_path)
    load_time = time.time() - start_time
    print(f"说话人区分完成，耗时 {load_time:.2f} 秒")

    speaker_turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_turns.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker,
        })

    return speaker_turns


def _assign_speakers(
    segments: list[Segment],
    speaker_turns: list[dict],
) -> list[Segment]:
    for seg in segments:
        seg_start = seg.start
        seg_end = seg.end
        seg_mid = (seg_start + seg_end) / 2

        best_overlap = 0.0
        best_speaker = None

        for turn in speaker_turns:
            t_start = turn["start"]
            t_end = turn["end"]
            t_speaker = turn["speaker"]

            if seg_end <= t_start or seg_start >= t_end:
                continue

            overlap_start = max(seg_start, t_start)
            overlap_end = min(seg_end, t_end)
            overlap = overlap_end - overlap_start

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = t_speaker

        if best_speaker is None:
            for turn in speaker_turns:
                t_start = turn["start"]
                t_end = turn["end"]
                if t_start <= seg_mid <= t_end:
                    best_speaker = turn["speaker"]
                    break

        if best_speaker is not None:
            seg.speaker = best_speaker

    return segments
