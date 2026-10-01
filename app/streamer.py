import subprocess
import os
from typing import Generator, Optional
from datetime import datetime, timezone
from app.scheduler import get_currently_playing_slot, get_channel_schedule

def get_current_media_source(channel_id: int) -> Optional[dict]:
    """Find currently playing media file path or stream URL and start offset"""
    slot = get_currently_playing_slot(channel_id)
    if not slot:
        return None
    
    offset = slot.get("current_offset_seconds", 0)
    
    if slot["type"] == "main":
        source_url = slot.get("stream_url")
    else: # commercial
        file_path = slot.get("file_path")
        source_url = file_path if file_path and os.path.exists(file_path) else None
        
    return {
        "slot": slot,
        "source_url": source_url,
        "offset": offset
    }

def generate_mpegts_stream(channel_id: int) -> Generator[bytes, None, None]:
    """
    Spawns an ffmpeg process to transcode the active program/commercial starting at current offset,
    standardized to 1080p H.264/AAC MPEG-TS stream output.
    """
    media_info = get_current_media_source(channel_id)
    
    if not media_info or not media_info["source_url"]:
        # Output a 5-second black filler screen with audio if media source isn't ready
        cmd = [
            "ffmpeg",
            "-re",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "5",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-f", "mpegts", "pipe:1"
        ]
    else:
        source_url = media_info["source_url"]
        offset = max(0, int(media_info["offset"]))
        
        cmd = [
            "ffmpeg",
            "-ss", str(offset),
            "-re",
            "-i", source_url,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "4000k",
            "-maxrate", "4500k",
            "-bufsize", "9000k",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-f", "mpegts",
            "pipe:1"
        ]
        
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=1024*64)
    
    try:
        while True:
            chunk = proc.stdout.read(64 * 1024)
            if not chunk:
                break
            yield chunk
    finally:
        proc.kill()
        proc.wait()
