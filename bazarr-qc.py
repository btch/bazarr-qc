#!/usr/bin/env python3
import sys
import os

if len(sys.argv) != 7:
    print("Usage: <episode_id> <series_id> <provider> <subtitle_id> <subtitles_language> <subtitles>")
    sys.exit(1)

episode_id, series_id, provider, subtitle_id, subtitles_language, subtitles = sys.argv[1:7]
if provider == "embeddedsubtitles":
    print("Provider is embeddedsubtitles, proceeding with language check but skipping offset check.")

import sqlite3
import re
import subprocess
from datetime import datetime, timedelta
from urllib.parse import quote

sys.path.insert(0, "/app/bin/libs")
from guess_language import guess_language

# === CONFIGURATION ===
ALLOWED_OFFSET_SECONDS = 5.0  # Max allowed offset in seconds (+/-)
API_KEY = "YOUR_BAZARR_API_KEY"  # API key to Bazarr
API_HOST = "YOUR_IP"  # IP
API_PORT = "6767"  # Bazarr port
DB_PATH = "/db/bazarr.db"  # Path to Bazarr's database file
ENABLE_LOGGING = True  # Set False to disable logging to log-file.log
ENABLE_LANGUAGE_DETECTION = True  # Set False to disable subtitle language check

# === Setup Logging ===
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file_path = os.path.join(script_dir, "log-file.log")


def log(message):
    if not ENABLE_LOGGING:
        return
    timestamped = f"[{datetime.now().isoformat()}] {message}"
    with open(log_file_path, "a") as f:
        f.write(timestamped + "\n")


# === Language Detection Check ===

if ENABLE_LANGUAGE_DETECTION:
    try:
        with open(subtitles, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Remove timestamps, numeric lines, and blank lines
        dialogue_lines = []
        for line in lines:
            line = line.strip()
            if (
                    not line or
                    re.match(r"^\d+$", line) or
                    re.match(r"\d{2}:\d{2}:\d{2},\d{3} -->", line)
            ):
                continue
            dialogue_lines.append(line)

        cleaned_text = " ".join(dialogue_lines)[:10000]

        detected_lang = guess_language(cleaned_text)
        expected_lang = subtitles_language.split(":")[0].lower()

        print(f"[LANG DETECTION] Detected: {detected_lang}, Expected: {expected_lang}", flush=True)

        if not detected_lang or detected_lang.lower() != expected_lang:
            print("[ACTION] Blacklisting subtitle due to language mismatch...", flush=True)
            log(f"Blacklist due to language mismatch: Detected={detected_lang}, Expected={expected_lang}, Path={subtitles}")

            subtitles_encoded = quote(subtitles)
            subtitle_id_encoded = quote(subtitle_id)
            provider_encoded = quote(provider)
            language_encoded = quote(subtitles_language)

            if not series_id:
                url = (
                    f"http://{API_HOST}:{API_PORT}/api/movies/blacklist"
                    f"?radarrid={episode_id}"
                    f"&provider={provider_encoded}"
                    f"&subs_id={subtitle_id_encoded}"
                    f"&language={language_encoded}"
                    f"&subtitles_path={subtitles_encoded}"
                )
            else:
                url = (
                    f"http://{API_HOST}:{API_PORT}/api/episodes/blacklist"
                    f"?seriesid={series_id}"
                    f"&episodeid={episode_id}"
                    f"&provider={provider_encoded}"
                    f"&subs_id={subtitle_id_encoded}"
                    f"&language={language_encoded}"
                    f"&subtitles_path={subtitles_encoded}"
                )

            curl_cmd = [
                "curl", "--silent", "--show-error", "-X", "POST",
                url,
                "-H", "accept: application/json",
                "-H", f"X-API-KEY: {API_KEY}",
                "-d", ""
            ]

            try:
                result = subprocess.run(curl_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print("[SUCCESS] Blacklist request sent for language mismatch.", flush=True)
                else:
                    msg = (f"[ERROR] Curl failed during language mismatch blacklist\n"
                           f"Return code: {result.returncode}\n"
                           f"STDOUT:\n{result.stdout.strip()}\n"
                           f"STDERR:\n{result.stderr.strip()}")
                    print(msg, flush=True)
                    log(msg)
            except Exception as e:
                msg = f"[ERROR] Curl execution failed (lang mismatch): {str(e)}"
                print(msg, flush=True)
                log(msg)

    except Exception as e:
        print(f"[LANG DETECTION ERROR] {e}", flush=True)
        print("no", flush=True)
else:
    print("[INFO] Language detection is disabled.", flush=True)

# === MAIN SCRIPT BELOW ===

if provider != "embeddedsubtitles":
    if not episode_id:
        msg = "[ERROR] No episode_id provided."
        print(msg, flush=True)
        log(msg)
        exit(1)

    if not os.path.exists(DB_PATH):
        msg = f"[ERROR] Database not found at {DB_PATH}"
        print(msg, flush=True)
        log(msg)
        exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        if not series_id:
            table = "table_history_movie"
            id_column = "radarrId"
        else:
            table = "table_history"
            id_column = "sonarrEpisodeId"

        now = datetime.now()
        two_hours_ago = now - timedelta(hours=2)

        query = f"""
            SELECT id, description, timestamp FROM {table}
            WHERE {id_column} = ? AND action = 5 AND language LIKE ?
            ORDER BY id DESC
            LIMIT 1
        """
        cursor.execute(query, (episode_id, f"{subtitles_language}%"))
        row = cursor.fetchone()

        if not row:
            msg = "[WARN] No matching 'action = 5' row found."
            print(msg, flush=True)
            log(msg)
            exit(0)

        match_id, description, ts_string = row

        try:
            entry_time = datetime.strptime(ts_string, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            msg = f"[ERROR] Failed to parse timestamp: {ts_string}"
            print(msg, flush=True)
            log(msg)
            exit(1)

        if entry_time < two_hours_ago:
            msg = f"[INFO] Skipping match. Timestamp {entry_time} is older than 2 hours."
            print(msg, flush=True)
            log(msg)
            exit(0)

        match = re.search(r'offset of ([\d.-]+) seconds', description)
        if not match:
            msg = "[ERROR] Offset pattern not found in description."
            print(msg, flush=True)
            log(msg)
            exit(0)

        offset = float(match.group(1))
        print(f"[SUCCESS] Extracted offset: {offset} seconds", flush=True)

        if abs(offset) > ALLOWED_OFFSET_SECONDS:
            print(f"[ALERT] Offset exceeds ±{ALLOWED_OFFSET_SECONDS} seconds.", flush=True)

            subtitles_encoded = quote(subtitles)
            subtitle_id_encoded = quote(subtitle_id)
            provider_encoded = quote(provider)
            language_encoded = quote(subtitles_language)

            if not series_id:
                print("[ACTION] Blacklisting subtitle for movie...", flush=True)
                log(f"Movie: Offset={offset}, ID={episode_id}, SubID={subtitle_id}, Lang={subtitles_language}, Path={subtitles}")
                url = (
                    f"http://{API_HOST}:{API_PORT}/api/movies/blacklist"
                    f"?radarrid={episode_id}"
                    f"&provider={provider_encoded}"
                    f"&subs_id={subtitle_id_encoded}"
                    f"&language={language_encoded}"
                    f"&subtitles_path={subtitles_encoded}"
                )
            else:
                print("[ACTION] Blacklisting subtitle for series...", flush=True)
                log(f"Series: Offset={offset}, SeriesID={series_id}, EpisodeID={episode_id}, SubID={subtitle_id}, Lang={subtitles_language}, Path={subtitles}")
                url = (
                    f"http://{API_HOST}:{API_PORT}/api/episodes/blacklist"
                    f"?seriesid={series_id}"
                    f"&episodeid={episode_id}"
                    f"&provider={provider_encoded}"
                    f"&subs_id={subtitle_id_encoded}"
                    f"&language={language_encoded}"
                    f"&subtitles_path={subtitles_encoded}"
                )

            curl_cmd = [
                "curl", "--silent", "--show-error", "-X", "POST",
                url,
                "-H", "accept: application/json",
                "-H", f"X-API-KEY: {API_KEY}",
                "-d", ""
            ]

            try:
                result = subprocess.run(curl_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print("[SUCCESS] Blacklist request sent.", flush=True)
                else:
                    msg = (f"[ERROR] Curl failed with return code {result.returncode}\n"
                           f"STDOUT:\n{result.stdout.strip()}\n"
                           f"STDERR:\n{result.stderr.strip()}")
                    print(msg, flush=True)
                    log(msg)
            except Exception as e:
                msg = f"[ERROR] Curl execution failed: {str(e)}"
                print(msg, flush=True)
                log(msg)
        else:
            print(f"[INFO] Offset is within acceptable range ±{ALLOWED_OFFSET_SECONDS} seconds. No action taken.",
                  flush=True)

    finally:
        conn.close()
