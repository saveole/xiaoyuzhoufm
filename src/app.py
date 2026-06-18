import streamlit as st
import torch
import time
import os
from pydub import AudioSegment

torch.classes.__path__ = []

from download import fetch_audio_file
from transcribe import transcribe_audio
from models import EpisodeMeta
from exporters import export as export_segments
from config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, HF_TOKEN

st.set_page_config(page_title="小宇宙播客工具", layout="wide")
st.title("小宇宙播客下载与转录工具")

if "download_completed" not in st.session_state:
    st.session_state.download_completed = False
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "episode_meta" not in st.session_state:
    st.session_state.episode_meta = EpisodeMeta(title="")
if "segments" not in st.session_state:
    st.session_state.segments = []
if "transcript_text" not in st.session_state:
    st.session_state.transcript_text = ""
if "is_transcribing" not in st.session_state:
    st.session_state.is_transcribing = False
if "is_diarizing" not in st.session_state:
    st.session_state.is_diarizing = False
if "is_correcting" not in st.session_state:
    st.session_state.is_correcting = False
if "speaker_map" not in st.session_state:
    st.session_state.speaker_map = {}
if "corrected_segments" not in st.session_state:
    st.session_state.corrected_segments = []
if "transcribe_info" not in st.session_state:
    st.session_state.transcribe_info = {}


def format_duration(seconds: float) -> str:
    seconds = round(seconds)
    hours = seconds // 3600
    remaining = seconds % 3600
    minutes = remaining // 60
    secs = remaining % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}分")
    parts.append(f"{secs}秒")
    return "".join(parts)


# ============================================================
# 第一步：下载
# ============================================================
download_expander = st.expander(
    "第一步：下载播客", expanded=not st.session_state.download_completed
)
with download_expander:
    url = st.text_input("请输入小宇宙播客链接：")

    if st.button("开始下载"):
        if url:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                def update_progress(progress):
                    progress_bar.progress(progress)
                    status_text.text(f"下载进度：{int(progress * 100)}%")

                audio_path, meta = fetch_audio_file(url, update_progress)
                st.session_state.audio_path = audio_path
                st.session_state.episode_meta = meta
                st.session_state.download_completed = True
                status_text.text("下载完成！")
                st.success(f"成功下载播客：{meta.title}")
            except Exception as e:
                st.error(f"下载失败：{str(e)}")
        else:
            st.warning("请输入有效的播客链接")

if st.session_state.download_completed:
    meta = st.session_state.episode_meta

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"**{meta.title}**")
        if meta.podcast:
            st.text(f"播客：{meta.podcast}")
        if meta.hosts:
            st.text(f"主播：{'、'.join(meta.hosts)}")
        if meta.guests:
            st.text(f"嘉宾：{'、'.join(meta.guests)}")

    with col2:
        audio = AudioSegment.from_file(st.session_state.audio_path)
        duration_sec = audio.duration_seconds
        st.text(f"音频长度：{format_duration(duration_sec)}")
        st.text(f"音频大小：{os.path.getsize(st.session_state.audio_path) / 1024 / 1024:.2f} MB")
        st.audio(st.session_state.audio_path)

    if meta.shownotes:
        with st.expander("查看 Shownotes"):
            st.markdown(meta.shownotes)

# ============================================================
# 第二步：转录 + 后处理
# ============================================================
transcribe_expander = st.expander(
    "第二步：转录音频", expanded=st.session_state.download_completed
)
with transcribe_expander:
    if st.session_state.download_completed:
        st.info("提示：一分钟的音频大约需要 10 秒转录时间（不同设备转录时间不同）")

        device_map = {"CPU": "cpu"}
        selected_device = st.selectbox("选择运行设备：", list(device_map.keys()))

        output_format = st.selectbox("选择输出格式：", ["txt", "srt", "md", "pdf"])

        enable_diarize = st.checkbox(
            "区分说话人",
            value=False,
            help="使用 pyannote 进行说话人区分。需配置 HF_TOKEN。首次运行会下载 ~3GB 模型。",
        )
        if enable_diarize and not HF_TOKEN:
            st.warning("HF_TOKEN 未配置，说话人区分将不可用。请在 .env 文件中设置 HF_TOKEN。")

        enable_correct = st.checkbox(
            "AI 修正转录",
            value=False,
            help="使用 LLM 修正 ASR 错误。需配置 LLM_API_KEY。",
        )
        if enable_correct:
            if LLM_API_KEY:
                model_options = [LLM_MODEL, "deepseek-chat", "glm-4-flash", "moonshot-v1-8k"]
                selected_model = st.selectbox(
                    "修正模型：", model_options,
                    index=0 if LLM_MODEL in model_options else 0,
                )
            else:
                st.warning("LLM_API_KEY 未配置，AI 修正将不可用。请在 .env 文件中配置。")

        if st.button("开始转录", disabled=st.session_state.is_transcribing):
            try:
                st.session_state.is_transcribing = True
                status_text = st.empty()
                status_text.text("转录中...")

                start_time = time.time()
                audio_length_minutes = duration_sec / 60
                estimated_time = audio_length_minutes * 6
                st.info(f"预计转录时间：{estimated_time/60:.2f} 分钟")

                segments, info = transcribe_audio(
                    st.session_state.audio_path,
                    device_map[selected_device],
                    show_progress=False,
                )

                st.session_state.segments = segments
                st.session_state.transcribe_info = info
                elapsed = time.time() - start_time
                status_text.text("转录完成！")
                st.success(f"转录完成！耗时：{elapsed:.2f} 秒，共 {len(segments)} 个片段")

                # 说话人区分
                if enable_diarize and HF_TOKEN:
                    st.session_state.is_diarizing = True
                    diarize_status = st.empty()
                    diarize_status.text("正在区分说话人...")
                    try:
                        from diarize import diarize_audio
                        segments = diarize_audio(
                            st.session_state.audio_path,
                            segments,
                        )
                        st.session_state.segments = segments
                        st.session_state.speaker_map = {}
                        diarize_status.text("说话人区分完成！")
                    except Exception as e:
                        st.warning(f"说话人区分失败：{str(e)}，将继续使用无说话人版本")
                    finally:
                        st.session_state.is_diarizing = False

                # AI 修正
                if enable_correct and LLM_API_KEY:
                    st.session_state.is_correcting = True
                    correct_status = st.empty()
                    correct_status.text("正在 AI 修正...")
                    try:
                        from correct import correct_segments
                        corrected = correct_segments(
                            segments,
                            st.session_state.episode_meta,
                            model=selected_model if enable_correct else None,
                        )
                        st.session_state.corrected_segments = corrected
                        correct_status.text("AI 修正完成！")
                    except Exception as e:
                        st.warning(f"AI 修正失败：{str(e)}，将使用原始转录")
                    finally:
                        st.session_state.is_correcting = False

                st.session_state.is_transcribing = False
                st.rerun()

            except Exception as e:
                st.error(f"转录失败：{str(e)}")
                st.session_state.is_transcribing = False
    else:
        st.info("请先完成播客下载")

# ============================================================
# 说话人映射 UI
# ============================================================
if st.session_state.segments and not st.session_state.is_transcribing:
    segments = st.session_state.segments
    meta = st.session_state.episode_meta

    speakers_in_use = sorted(set(
        seg.speaker for seg in segments if seg.speaker
    ))

    if speakers_in_use:
        st.subheader("说话人映射")
        st.caption("将自动识别的说话人标签映射到真实姓名")

        candidates = ["不标注"]
        candidates.extend(meta.hosts)
        candidates.extend(meta.guests)
        for s in speakers_in_use:
            if s not in candidates:
                candidates.append(s)
        candidates = list(dict.fromkeys(candidates))

        new_map = {}
        cols = st.columns(len(speakers_in_use))
        for i, speaker in enumerate(speakers_in_use):
            with cols[i]:
                default_idx = 0
                if speaker in st.session_state.speaker_map:
                    mapped = st.session_state.speaker_map[speaker]
                    if mapped in candidates:
                        default_idx = candidates.index(mapped)
                selected = st.selectbox(
                    speaker,
                    candidates,
                    index=default_idx,
                    key=f"speaker_map_{speaker}",
                )
                if selected != "不标注":
                    new_map[speaker] = selected

        if new_map and st.button("应用说话人映射"):
            from names import guess_speaker_names
            st.session_state.segments = guess_speaker_names(
                segments, meta, new_map
            )
            st.session_state.speaker_map = new_map
            if st.session_state.corrected_segments:
                st.session_state.corrected_segments = guess_speaker_names(
                    st.session_state.corrected_segments, meta, new_map
                )
            st.success("说话人映射已应用！")
            st.rerun()

# ============================================================
# 结果预览与导出
# ============================================================
if st.session_state.segments and not st.session_state.is_transcribing:
    st.subheader("转录文稿")

    segments_to_export = (
        st.session_state.corrected_segments
        if st.session_state.corrected_segments
        else st.session_state.segments
    )

    fmt_from_ui = st.selectbox(
        "预览/导出格式：",
        ["txt", "srt", "md", "pdf"],
        key="preview_format",
    )

    out_filename = f"{st.session_state.episode_meta.title}.{fmt_from_ui}"
    safe_name = "".join(c for c in out_filename if c.isalnum() or c in " ._-").strip()
    if not safe_name:
        safe_name = f"transcript.{fmt_from_ui}"
    out_path = os.path.join("audio_files", safe_name)

    try:
        content = export_segments(
            segments_to_export,
            st.session_state.episode_meta,
            fmt_from_ui,
            out_path,
        )
    except Exception as e:
        st.error(f"导出失败：{str(e)}")
        st.warning("导出出错，请重试或切换格式")
        st.stop()

    if fmt_from_ui == "md":
        st.markdown(content)
        st.download_button(
            label="下载 MD 文件",
            data=content,
            file_name=safe_name,
            mime="text/markdown",
        )
    elif fmt_from_ui == "pdf":
        st.success(f"PDF 已生成：{out_path}")
        with open(out_path, "rb") as f:
            st.download_button(
                label="下载 PDF",
                data=f,
                file_name=safe_name,
                mime="application/pdf",
            )
        with st.expander("预览 PDF 文字内容"):
            st.markdown(content)
    else:
        st.text_area("转录预览", content, height=400)
        mime_map = {"txt": "text/plain", "srt": "text/plain"}
        st.download_button(
            label=f"下载 {fmt_from_ui.upper()} 文件",
            data=content,
            file_name=safe_name,
            mime=mime_map.get(fmt_from_ui, "application/octet-stream"),
        )

    # 修正前后对比
    if st.session_state.corrected_segments:
        with st.expander("查看修正前后对比"):
            orig = st.session_state.segments
            corr = st.session_state.corrected_segments
            diffs = []
            for i, (o, c) in enumerate(zip(orig, corr)):
                if o.text.strip() != c.text.strip():
                    diffs.append((i, o.text.strip(), c.text.strip()))
            if diffs:
                st.caption(f"共 {len(diffs)} 处修改")
                for idx, orig_t, corr_t in diffs[:20]:
                    st.markdown(f"**片段 {idx}**")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.text_area("原始", orig_t, height=80, key=f"orig_{idx}")
                    with col_b:
                        st.text_area("修正后", corr_t, height=80, key=f"corr_{idx}")
                if len(diffs) > 20:
                    st.info(f"还有 {len(diffs) - 20} 处修改未显示")
            else:
                st.info("未检测到差异")
