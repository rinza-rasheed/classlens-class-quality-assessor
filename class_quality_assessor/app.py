import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="ClassLens | Recording Quality", page_icon="🎓", layout="centered")

st.markdown("""
<style>
.block-container {max-width: 900px; padding-top: 2.2rem;}
.hero {padding: 1.5rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg,#eef2ff,#f0fdfa); margin-bottom: 1rem;}
.muted {color:#64748b;}
</style>
<div class="hero">
  <h1>🎓 ClassLens</h1>
  <p>AI-powered assessment for online class recordings</p>
  <p class="muted">Review clarity, teaching structure, engagement, and recording quality—with evidence-based observations.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Gemini API key", type="password", help="Get a key from Google AI Studio. It is used only for this session.")
    model = st.selectbox("AI model", ["gemini-2.5-flash", "gemini-2.0-flash"], index=0)
    st.caption("Your API key is not saved by this app.")

st.write("Choose a recording file or provide a direct video link. For private recordings, upload the file instead of sharing a restricted link.")
mode = st.radio("Recording source", ["Upload a file", "Paste a link"], horizontal=True)

uploaded = None
video_url = ""
if mode == "Upload a file":
    uploaded = st.file_uploader("Upload class recording", type=["mp4", "mov", "webm", "m4v", "mp3", "wav", "m4a", "mpga"])
    st.caption("Supported formats depend on Gemini's current media support. Keep files reasonably sized.")
else:
    video_url = st.text_input("Direct or publicly accessible video URL", placeholder="https://…")
    st.caption("The link must be publicly accessible and downloadable by this app. YouTube links may not work as direct media URLs.")

with st.expander("What does the assessment consider?"):
    st.markdown("""
    - **Teaching & structure:** clear objectives, logical flow, explanations and examples.
    - **Audio & visual quality:** intelligibility, noise, volume consistency, visibility of slides or writing.
    - **Engagement & pacing:** questions, checks for understanding, pauses and pace.
    - **Evidence & improvement:** concrete moments or patterns and practical next steps.

    The rating reflects the recording available to the model; it is not a definitive measure of teaching ability or student learning.
    """)

def wait_for_file(client, file_obj):
    current = file_obj
    for _ in range(60):
        state = getattr(current, "state", None)
        state_name = getattr(state, "name", str(state)).upper() if state is not None else ""
        if "ACTIVE" in state_name:
            return current
        if "FAILED" in state_name:
            raise RuntimeError("Gemini could not process this media file. Try an MP4 or MP3 recording.")
        time.sleep(2)
        current = client.files.get(name=current.name)
    raise TimeoutError("Media processing took too long. Try a shorter recording.")

def assess_media(client, file_obj, model_name):
    prompt = """
You are an expert reviewer of online class recordings. Assess only what can reasonably be observed in this recording.
Return a clear report with these sections:
1. Overall rating: exactly one of Poor, Average, Good, Excellent.
2. Confidence: High, Medium, or Low, with one short reason.
3. Scorecard: rate each area from 1–5 and explain briefly:
   - Audio clarity and consistency
   - Visual clarity / screen or board readability
   - Teaching structure and explanation
   - Pacing and engagement
   - Accessibility and learner support (e.g. verbal signposting, captions if visible)
   Use "Not assessable" if the recording does not provide enough evidence.
4. Specific observations: 3–6 bullets. Give concrete evidence from the recording. Include timestamps when you can identify them reliably; do not invent timestamps, quotations, or events.
5. What works well: 2–3 specific points.
6. Highest-impact improvements: 3 actionable changes, tied to observed issues.
7. Brief rationale: explain why the overall rating fits.
8. Limitations: mention anything the video/audio alone cannot establish.

Rating guide:
- Poor: serious issues repeatedly prevent access to or understanding of the class.
- Average: understandable overall, but several noticeable issues limit the experience.
- Good: clear and well-organized with only minor issues.
- Excellent: consistently clear, engaging, accessible, and well-structured.
Be balanced and respectful. Do not infer student outcomes or learner engagement from silence alone. If the media is not a class recording or is too short to assess, say so and use Low confidence.
"""
    response = client.models.generate_content(
        model=model_name,
        contents=[types.Part.from_uri(file_uri=file_obj.uri, mime_type=file_obj.mime_type), prompt],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return response.text or "The model returned an empty assessment."

def save_upload(file):
    suffix = Path(file.name).suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(file.getvalue())
    tmp.close()
    return tmp.name, file.name

def download_url(url):
    # Direct downloadable links only; deliberately avoid executing arbitrary shell commands.
    import requests
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid http:// or https:// URL.")
    response = requests.get(url, timeout=45, stream=True, headers={"User-Agent": "ClassLens/1.0"})
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    ext = Path(urlparse(response.url).path).suffix.lower()
    allowed = {".mp4", ".mov", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".mpga"}
    if ext not in allowed:
        ext = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
               "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/mp4": ".m4a"}.get(content_type, "")
    if not ext:
        raise ValueError("This does not look like a direct audio/video file URL. Upload the recording or use a direct media link.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    size = 0
    max_bytes = 500 * 1024 * 1024
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            size += len(chunk)
            if size > max_bytes:
                tmp.close()
                os.unlink(tmp.name)
                raise ValueError("The file exceeds the 500 MB download limit.")
            tmp.write(chunk)
    tmp.close()
    return tmp.name, Path(urlparse(response.url).path).name or "linked-recording" + ext

if st.button("Assess recording", type="primary", use_container_width=True):
    if not api_key:
        st.error("Add your Gemini API key in Settings to run the assessment.")
    elif not uploaded and not video_url.strip():
        st.error("Upload a recording or paste a link first.")
    else:
        local_path = None
        remote_file = None
        try:
            client = genai.Client(api_key=api_key)
            with st.status("Preparing recording and running the assessment…", expanded=True) as status:
                if uploaded:
                    local_path, display_name = save_upload(uploaded)
                else:
                    st.write("Downloading the media link…")
                    local_path, display_name = download_url(video_url.strip())
                size_mb = os.path.getsize(local_path) / (1024 * 1024)
                st.write(f"Recording ready: **{display_name}** ({size_mb:.1f} MB)")
                st.write("Uploading media securely to Gemini for analysis…")
                mime = {
                    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
                    ".m4v": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
                    ".m4a": "audio/mp4", ".mpga": "audio/mpeg"
                }.get(Path(local_path).suffix.lower(), "video/mp4")
                remote_file = client.files.upload(
                    file=local_path,
                    config=types.UploadFileConfig(display_name=display_name, mime_type=mime)
                )
                remote_file = wait_for_file(client, remote_file)
                st.write("Reviewing teaching, audio, visuals, pacing, and specific evidence…")
                report = assess_media(client, remote_file, model)
                status.update(label="Assessment complete", state="complete", expanded=False)
            st.session_state["report"] = report
            st.session_state["recording_name"] = display_name
        except Exception as e:
            st.error(f"Assessment failed: {e}")
            st.info("Check your API key, media format, file size, and whether the link is directly downloadable. You can also try a shorter recording.")
        finally:
            if local_path and os.path.exists(local_path):
                try:
                    os.unlink(local_path)
                except OSError:
                    pass
            # The uploaded media is kept only as long as Gemini's file retention permits.
            # Delete the remote file after analysis where supported.
            if remote_file is not None:
                try:
                    client.files.delete(name=remote_file.name)
                except Exception:
                    pass

if st.session_state.get("report"):
    st.divider()
    st.subheader("Assessment report")
    st.caption(st.session_state.get("recording_name", "Class recording"))
    st.markdown(st.session_state["report"])
    st.download_button(
        "Download report (.md)",
        data="# ClassLens — Class Recording Quality Assessment\n\n" + st.session_state["report"],
        file_name="class_quality_assessment.md",
        mime="text/markdown",
        use_container_width=True
    )

st.divider()
st.caption("ClassLens is a decision-support tool. Review its observations before using them for formal evaluation.")
