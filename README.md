# ChannelBuilder 📺

**ChannelBuilder** is a lightweight, Dockerized 24-hour virtual linear channel generator built specifically for **Jellyfin** content, **YouTube / Local** commercial breaks, and seamless ingest into **Dispatcharr** or any IPTV client.

Inspired by tools like *Tunarr*, *ErsatzTV*, *TubeSync*, *PinchFlat*, and *ytdl-sub*, ChannelBuilder combines your existing media library into continuous, retro-style TV channels with automated 2-minute commercial breaks.

---

## Key Features

1. **Jellyfin as Content Source**: Connects directly to your Jellyfin API to fetch TV shows, seasons, episodes, and movies with full metadata, images, and stream endpoints.
2. **YouTube & Local Commercial Breaks**:
   - Downloads commercial clips from YouTube playlists/videos using `yt-dlp` directly into a local cache.
   - Or scans a local directory for commercial clips (`.mp4`, `.mkv`, `.ts`, etc.).
   - Automatically algorithmically selects clips to build target **2-minute commercial breaks** between shows/movies.
3. **24-Hour Channel Generator**:
   - Create multiple virtual channels with custom channel numbers, names, and logos.
   - Option for **TV Shows** or **Movies** as main content.
   - Auto-shuffles content into endless, continuous 24-hour schedules with timed commercial breaks.
4. **Dispatcharr & IPTV Ingest**:
   - Generates standard `#EXTM3U` playlist (`/playlist.m3u`).
   - Generates standard `XMLTV` EPG guide (`/epg.xml`).
   - Streams live 1080p H.264 / AAC video output (`/stream/{channel_id}/live.ts`).

---

## Quick Start (Docker Compose)

### 1. Build and Start Container
From the project directory:
```bash
docker compose up -d --build
```

Access the Web Dashboard at **`http://localhost:8000`**.

### 2. Configure Jellyfin
1. Go to **Settings** in the Web Dashboard.
2. Enter your Jellyfin server URL (e.g. `http://192.168.1.50:8096` or `http://jellyfin:8096`).
3. Enter your Jellyfin API Key (generate one in Jellyfin Admin -> Settings -> API Keys).
4. Click **Save & Test Connection**.

### 3. Create a 24-Hour Channel
1. Go to **Channels** -> **Create Channel**.
2. Give your channel a number, name, and optional logo URL.
3. Select your content type (**TV Shows** or **Movies**).
4. Check the shows/movies from your Jellyfin library that you want on this channel.
5. Provide a YouTube playlist URL (or specify local path `/app/commercials_local`).
6. Click **Create & Download Commercials**.

---

## Dispatcharr / Jellyfin Live TV Setup

To add your virtual channels to **Dispatcharr**:

1. Open **Dispatcharr** (or IPTV client / Jellyfin Live TV settings).
2. Add a new **M3U Tuner**:
   - M3U URL: `http://<channel-builder-host>:8000/playlist.m3u`
3. Add a new **XMLTV EPG Provider**:
   - EPG URL: `http://<channel-builder-host>:8000/epg.xml`
4. Map channels and enjoy your 24/7 simulated TV experience!

---

## Project Structure

```
channel-builder/
├── docker-compose.yml       # Docker Compose setup with persistent volumes
├── Dockerfile               # Python 3.11 + ffmpeg + yt-dlp container definition
├── requirements.txt         # FastAPI, uvicorn, yt-dlp, requests dependencies
├── README.md
├── app/
│   ├── main.py              # FastAPI application & REST endpoints
│   ├── config.py            # Storage & stream encoding settings
│   ├── database.py          # SQLite database interface
│   ├── jellyfin.py          # Jellyfin API client
│   ├── youtube.py           # yt-dlp YouTube commercial manager & downloader
│   ├── commercials.py       # Commercial break selection engine
│   ├── scheduler.py         # 24-hour timeline schedule generator
│   ├── epg.py               # XMLTV EPG generator (/epg.xml)
│   ├── m3u.py               # M3U playlist generator (/playlist.m3u)
│   ├── streamer.py          # FFmpeg live stream transcoder
│   └── templates/           # Web UI templates (Tailwind CSS)
```
