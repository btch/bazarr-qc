# Subtitle QC based on offset value from audio-sync

This script automates the blacklisting of downloaded subtitles in Bazarr.  
It checks:

- ✅ Subtitle-to-video sync accuracy (based on Bazarr logs)
- ✅ Detected subtitle language vs. expected language
- ✅ Automatically blacklists out-of-sync subtitles and start a search for new. (configurable acceptable amount)

---

## 📂 Files

- `extract_sync_offsets.py`: Main Python script that performs offset-extraction, blacklisting and language checks.
- `postprocess.sh`: Bash wrapper that passes arguments from Bazarr and triggers the Python script.

---

## ⚙️ How It Works

When Bazarr downloads a subtitle, `postprocess.sh` is executed via the post-processing hook. It:

1. Exports subtitle metadata (IDs, language, file path).
2. Runs `extract_sync_offsets.py` with that context.
3. The Python script:
   - Reads Bazarr's SQLite DB for offset info.
   - Detects subtitle language (optional).
   - If an offset of more than +-5 seconds is found, blacklists the subtitle using Bazarr's API.

---

## 🔧 Configuration

Edit the top of `extract_sync_offsets.py` to adjust:

```python
ALLOWED_OFFSET_SECONDS = 5.0  # Max allowed offset (+/-) before blacklist
API_KEY = "your_api_key_here"
API_HOST = "your_ip"
API_PORT = "6767"
DB_PATH = "/config/db/bazarr.db"

ENABLE_LOGGING = True                 # Log actions to file
ENABLE_LANGUAGE_DETECTION = True     # Detect language using guess_language
