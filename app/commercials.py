import random
from typing import List, Dict, Any
from app.youtube import get_channel_commercial_clips

def build_commercial_break(channel_id: int, target_seconds: int = 120) -> List[Dict[str, Any]]:
    """
    Selects a sequence of commercial clips to total approximately target_seconds (e.g., 2 mins / 120s).
    """
    available_clips = get_channel_commercial_clips(channel_id)
    
    if not available_clips:
        # Fallback dummy break if no commercials downloaded yet
        return [{
            "id": "commercial_filler",
            "type": "commercial",
            "title": "Commercial Break",
            "file_path": None,
            "duration_seconds": float(target_seconds),
            "is_filler": True
        }]
    
    selected = []
    current_duration = 0.0
    clips_pool = list(available_clips)
    random.shuffle(clips_pool)
    
    # Fill until we reach or slightly exceed target duration (with max iterations limit)
    attempts = 0
    while current_duration < target_seconds and attempts < 20:
        attempts += 1
        clip = random.choice(clips_pool)
        selected.append({
            "id": f"comm_{clip['id']}_{len(selected)}",
            "type": "commercial",
            "title": f"Commercial: {clip['title']}",
            "file_path": clip["file_path"],
            "duration_seconds": float(clip["duration_seconds"]),
            "is_filler": False
        })
        current_duration += clip["duration_seconds"]
        
    return selected
