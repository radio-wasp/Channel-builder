import json
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from app.jellyfin import JellyfinClient
from app.commercials import build_commercial_break
from app.database import get_db, get_channel

def generate_channel_schedule(channel_id: int, duration_hours: int = 48) -> List[Dict[str, Any]]:
    """
    Generates a continuous timeline of slots (main content items + 2-min commercial breaks)
    covering duration_hours (e.g. past 24h to future 24h).
    """
    channel = get_channel(channel_id)
    if not channel:
        return []
    
    jellyfin = JellyfinClient()
    if not jellyfin.is_configured():
        return []
    
    content_type = channel.get("content_type", "tv")
    selected_items = channel.get("selected_items", [])
    shuffle_mode = channel.get("shuffle_mode", True)
    break_duration = channel.get("break_duration_seconds", 120)
    
    if not selected_items:
        return []
    
    # 1. Fetch main content items from Jellyfin
    main_pool: List[Dict[str, Any]] = []
    if content_type == "tv":
        for series_id in selected_items:
            eps = jellyfin.get_episodes_for_series(series_id)
            main_pool.extend(eps)
    else: # 'movie'
        for movie_id in selected_items:
            m = jellyfin.get_movie_item(movie_id)
            if m:
                main_pool.append(m)
                
    if not main_pool:
        return []
    
    # Shuffle pool if requested
    if shuffle_mode:
        random.shuffle(main_pool)
        
    # 2. Build continuous timeline starting 24h in the past
    now = datetime.now(timezone.utc)
    start_timeline = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
    end_target = start_timeline + timedelta(hours=duration_hours)
    
    current_time = start_timeline
    timeline_slots = []
    
    item_index = 0
    slot_id_counter = 1
    
    while current_time < end_target:
        # Get next item from pool (cycling infinitely)
        main_item = main_pool[item_index % len(main_pool)]
        item_index += 1
        
        main_duration = float(main_item.get("duration_seconds", 1800))
        item_start = current_time
        item_end = item_start + timedelta(seconds=main_duration)
        
        # Add Main Content Slot
        slot = {
            "slot_id": f"slot_{slot_id_counter}",
            "type": "main",
            "item_id": main_item["id"],
            "title": main_item.get("title", main_item.get("name", "Program")),
            "short_title": main_item.get("short_title", main_item.get("title", "Program")),
            "series_name": main_item.get("series_name"),
            "season_number": main_item.get("season_number"),
            "episode_number": main_item.get("episode_number"),
            "overview": main_item.get("overview", ""),
            "stream_url": main_item.get("stream_url"),
            "image_url": main_item.get("image_url"),
            "start_time": item_start.isoformat(),
            "end_time": item_end.isoformat(),
            "duration_seconds": main_duration
        }
        timeline_slots.append(slot)
        slot_id_counter += 1
        current_time = item_end
        
        # Add Commercial Break Slot (2 minutes)
        comm_clips = build_commercial_break(channel_id, target_seconds=break_duration)
        for clip in comm_clips:
            comm_dur = float(clip["duration_seconds"])
            comm_start = current_time
            comm_end = comm_start + timedelta(seconds=comm_dur)
            
            comm_slot = {
                "slot_id": f"slot_{slot_id_counter}",
                "type": "commercial",
                "item_id": clip.get("id"),
                "title": clip.get("title", "Commercial Break"),
                "short_title": "Commercial",
                "overview": "Sponsor Commercial Break",
                "file_path": clip.get("file_path"),
                "start_time": comm_start.isoformat(),
                "end_time": comm_end.isoformat(),
                "duration_seconds": comm_dur,
                "is_filler": clip.get("is_filler", False)
            }
            timeline_slots.append(comm_slot)
            slot_id_counter += 1
            current_time = comm_end

    # Save to SQLite database
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO schedules (channel_id, schedule_data, generated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (channel_id, json.dumps(timeline_slots)))
        conn.commit()

    return timeline_slots

def get_channel_schedule(channel_id: int) -> List[Dict[str, Any]]:
    """Fetch stored schedule or generate if missing"""
    with get_db() as conn:
        row = conn.execute("SELECT schedule_data FROM schedules WHERE channel_id = ?", (channel_id,)).fetchone()
        if row:
            try:
                return json.loads(row["schedule_data"])
            except Exception:
                pass
    return generate_channel_schedule(channel_id)

def get_currently_playing_slot(channel_id: int) -> Optional[Dict[str, Any]]:
    """Identify which program/commercial is playing right now on channel"""
    schedule = get_channel_schedule(channel_id)
    if not schedule:
        return None
    
    now = datetime.now(timezone.utc)
    for slot in schedule:
        st = datetime.fromisoformat(slot["start_time"])
        et = datetime.fromisoformat(slot["end_time"])
        if st <= now < et:
            offset = (now - st).total_seconds()
            slot_copy = dict(slot)
            slot_copy["current_offset_seconds"] = offset
            return slot_copy
            
    # If schedule expired, regenerate schedule
    schedule = generate_channel_schedule(channel_id)
    for slot in schedule:
        st = datetime.fromisoformat(slot["start_time"])
        et = datetime.fromisoformat(slot["end_time"])
        if st <= now < et:
            offset = (now - st).total_seconds()
            slot_copy = dict(slot)
            slot_copy["current_offset_seconds"] = offset
            return slot_copy
            
    return None
