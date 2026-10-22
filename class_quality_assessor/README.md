# ClassLens — Online Class Recording Quality Assessor

A small Streamlit application that accepts an uploaded class recording or a direct downloadable media URL, sends it to Google's Gemini API, and produces a rating of **Poor, Average, Good, or Excellent** with specific observations and practical recommendations.

## Requirements

- Python 3.10+
- A Gemini API key from Google AI Studio
- Internet access for package installation and model calls

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit (usually http://localhost:8501). Enter your Gemini API key in the sidebar, upload a media file or paste a **direct downloadable** audio/video URL, then click **Assess recording**.

## What the report covers

- Overall rating and confidence
- Audio and visual clarity
- Teaching structure and explanation
- Pacing and engagement
- Accessibility and learner support
- Specific observations, timestamps when reliably available, strengths, and actionable improvements
- Limitations of what can be inferred from a recording

## Important notes

- The link input expects a direct media file URL. Links requiring login, expiring signatures, or a video-platform page may not work. Upload the file in those cases.
- Model and API availability, file-size limits, and supported formats depend on your Gemini account and current API limits.
- The API key is entered at runtime and is not written to a file by this app. Do not deploy this demo publicly without adding authentication, upload limits, rate limiting, and privacy controls.
- Media is uploaded to Gemini for analysis and the app attempts to delete the remote file afterward. Review Google's current API data-retention terms before using recordings containing personal or confidential information.
- The score is an AI-supported review, not a definitive measure of teaching ability or learning outcomes. Always review the evidence, especially for formal decisions.
