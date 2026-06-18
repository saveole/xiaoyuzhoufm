import argparse
from faster_whisper import WhisperModel
import os
import time
from functools import lru_cache
from typing import Optional

from models import Segment
from exporters import export as export_segments
from exporters.txt import export as export_txt
from exporters.srt import export as export_srt


@lru_cache(maxsize=8)
def get_whisper_model(model_size="turbo", device="cpu", compute_type="int8"):
    print(f"加载 Whisper 模型 ({model_size}) 到 {device}...")
    start_time = time.time()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    load_time = time.time() - start_time
    print(f"模型加载完成，耗时 {load_time:.2f} 秒")
    return model


def transcribe_audio(
    audio_path: str,
    device_option: Optional[str] = None,
    beam_size: int = 5,
    show_progress: bool = True,
) -> tuple[list[Segment], dict]:
    start_time = time.time()

    if show_progress:
        print(f"音频路径: {audio_path}")
        print(f"设备选项: {device_option or 'auto'}")
        print(f"Beam size: {beam_size}")

    audio_size = os.path.getsize(audio_path)
    if show_progress:
        print(f"音频文件大小: {audio_size / (1024*1024):.2f} MB")

    compute_type = "float16" if device_option == "cuda" else "int8"
    model = get_whisper_model("turbo", device_option, compute_type)

    if show_progress:
        print("开始音频转录...")

    segments_gen, info = model.transcribe(
        audio_path,
        beam_size=beam_size,
        word_timestamps=True,
    )

    segments = []
    for seg in segments_gen:
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip(),
        ))

    if show_progress:
        print("音频转录完成！")
        print(f"检测到语言：{info.language} (概率: {info.language_probability:.3f})")
        processing_time = time.time() - start_time
        audio_duration = info.duration
        speed_ratio = audio_duration / processing_time if processing_time > 0 else 0
        print(f"音频时长: {audio_duration:.2f} 秒")
        print(f"处理耗时: {processing_time:.2f} 秒")
        print(f"处理速度: {speed_ratio:.2f}x 实时")

    return segments, {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "processing_time": time.time() - start_time,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用 faster‑whisper 模型进行音频转录。")
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入音频文件的路径"
    )
    parser.add_argument(
        "-o", "--output",
        default="transcription_output.txt",
        help="转录文本的输出文件路径"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["txt", "srt"],
        default="txt",
        help="输出文件格式"
    )
    parser.add_argument(
        "-d", "--device",
        default=None,
        help="指定使用的设备：cuda、cpu 或 mps"
    )
    parser.add_argument(
        "-b", "--beam-size",
        type=int,
        default=5,
        help="beam search 大小"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="不显示进度信息"
    )
    args = parser.parse_args()

    from models import EpisodeMeta

    segments, info = transcribe_audio(
        args.input,
        args.device,
        args.beam_size,
        not args.no_progress,
    )
    meta = EpisodeMeta(title=os.path.basename(args.input))
    export_segments(segments, meta, args.format, args.output)
