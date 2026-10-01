import subprocess
import json
import os
import glob
from pathlib import Path
from typing import List, Dict, Any
from app.config import COMMERCIAL_CACHE_DIR
from app.database import get_db

def get_video_duration(file_path: str) -> float:
    """Use ffprobe to probe file duration in seconds"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 30.0 # default fallback estimate

def download_youtube_commercials(channel_id: int, youtube_url: str, max_clips: int = 20) -> List[Dict[str, Any]]:
    """Download clips from YouTube playlist/video url using yt-dlp into local cache"""
    channel_cache_dir = COMMERCIAL_CACHE_DIR / str(channel_id)
    channel_cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch playlist info using yt-dlp json dump
    yt_dump_cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        youtube_url
    ]
    
    clips_processed = []
    try:
        proc = subprocess.run(yt_dump_cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            print(f"Error fetching YouTube info: {proc.stderr}")
            return []
        
        info = json.loads(proc.stdout)
        entries = info.get("entries", [info]) if "entries" in info else [info]
        
        # Limit max clips
        entries = entries[:max_clips]
        
        for entry in entries:
            video_id = entry.get("id")
            title = entry.get("title", f"Commercial {video_id}")
            if not video_id:
                continue
            
            output_template = str(channel_cache_dir / f"{video_id}.mp4")
            
            # If already downloaded, check if file exists
            if not os.path.exists(output_template):
                dl_cmd = [
                    "yt-dlp",
                    "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--merge-output-format", "mp4",
                    "-o", output_template,
                    f"https://www.youtube.com/watch?v={video_id}"
                ]
                print(f"Downloading YouTube commercial: {title} ({video_id})...")
                subprocess.run(dl_cmd, capture_output=True, text=True, timeout=120)
            
            if os.path.exists(output_template):
                duration = get_video_duration(output_template)
                
                # Save to database
                with get_db() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO commercial_clips 
                        (channel_id, title, source_type, source_identifier, file_path, duration_seconds)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (channel_id, title, "youtube", video_id, output_template, duration))
                    conn.commit()
                
                clips_processed.append({
                    "title": title,
                    "file_path": output_template,
                    "duration_seconds": duration
                })
    except Exception as e:
        print(f"Failed downloading commercials for channel {channel_id}: {e}")
        
    return clips_processed

def scan_local_commercials(channel_id: int, folder_path: str) -> List[Dict[str, Any]]:
    """Scan local directory for commercial media files and register duration"""
    p = Path(folder_path)
    if not p.exists() or not p.is_dir():
        print(f"Local commercial directory {folder_path} does not exist.")
        return []
    
    valid_exts = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".webm"}
    found_clips = []
    
    for item in p.rglob("*"):
        if item.is_file() and item.suffix.lower() in valid_exts:
            duration = get_video_duration(str(item))
            title = item.stem.replace("_", " ").title()
            
            with get_db() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO commercial_clips
                    (channel_id, title, source_type, source_identifier, file_path, duration_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (channel_id, title, "local", str(item.name), str(item), duration))
                conn.commit()
            
            found_clips.append({
                "title": title,
                "file_path": str(item),
                "duration_seconds": duration
            })
            
    return found_clips

def get_channel_commercial_clips(channel_id: int) -> List[Dict[str, Any]]:
    """Retrieve indexed commercial clips for a channel from SQLite"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM commercial_clips WHERE channel_id = ?", (channel_id,)).fetchall()
        return [dict(r) for r in rows]
