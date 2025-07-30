#!/bin/bash
set -eu

# Sonarr episode ID or Radarr movie ID
episode_id="$1"
# Sonarr series ID (Empty if movie)
series_id="$2"
# Provider
provider="$3"
# Provider ID of the subtitle file
subtitle_id="$4"
# Language of the subtitles file (may include HI or forced)
subtitles_language="$5"
# Full path of the subtitles file
subtitles="$6"


if [[ "$provider" != "embeddedsubtitles" ]]; then

    export episode_id
    export series_id
    export provider
    export subtitle_id
    export subtitles_language
    export subtitles

    python3 /config/extract_sync_offsets.py
else
    echo "Skipping post-processing. Subtitle provider is embeddedsubtitles"
fi
