import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
from app.database import get_channels
from app.scheduler import get_channel_schedule

def format_xmltv_date(dt: datetime) -> str:
    """Format datetime to XMLTV date string format: YYYYMMDDhhmmss +0000"""
    return dt.strftime("%Y%m%d%H%M%S +0000")

def generate_epg_xml(base_url: str = "") -> str:
    """
    Generates standard XMLTV EPG document containing channels and schedule listings.
    """
    tv_elem = ET.Element("tv", {"generator-info-name": "ChannelBuilder"})
    
    channels = get_channels()
    
    # 1. Add <channel> definitions
    for channel in channels:
        ch_id = f"channel.{channel['id']}"
        ch_elem = ET.SubElement(tv_elem, "channel", {"id": ch_id})
        
        display_name = ET.SubElement(ch_elem, "display-name")
        display_name.text = f"{channel['number']} {channel['name']}"
        
        if channel.get("logo_url"):
            ET.SubElement(ch_elem, "icon", {"src": channel["logo_url"]})
            
    # 2. Add <programme> definitions for each channel's schedule
    for channel in channels:
        ch_id = f"channel.{channel['id']}"
        schedule = get_channel_schedule(channel['id'])
        
        for slot in schedule:
            # Skip commercial breaks from EPG main title if desired, or present as "Commercial Break"
            st = datetime.fromisoformat(slot["start_time"])
            et = datetime.fromisoformat(slot["end_time"])
            
            prog_elem = ET.SubElement(tv_elem, "programme", {
                "start": format_xmltv_date(st),
                "stop": format_xmltv_date(et),
                "channel": ch_id
            })
            
            title_elem = ET.SubElement(prog_elem, "title", {"lang": "en"})
            title_elem.text = slot.get("title", "Program")
            
            desc_elem = ET.SubElement(prog_elem, "desc", {"lang": "en"})
            desc_elem.text = slot.get("overview") or ("Commercial Break" if slot["type"] == "commercial" else "")
            
            # Category
            cat_elem = ET.SubElement(prog_elem, "category", {"lang": "en"})
            cat_elem.text = "Commercial" if slot["type"] == "commercial" else ("TV Series" if channel["content_type"] == "tv" else "Movie")
            
            # Icon
            if slot.get("image_url"):
                ET.SubElement(prog_elem, "icon", {"src": slot["image_url"]})
                
            # XMLTV season/episode number formatting (xmltv_ns: season_idx . ep_idx .)
            if slot.get("season_number") is not None and slot.get("episode_number") is not None:
                s_idx = max(0, slot["season_number"] - 1)
                e_idx = max(0, slot["episode_number"] - 1)
                ep_elem = ET.SubElement(prog_elem, "episode-num", {"system": "xmltv_ns"})
                ep_elem.text = f"{s_idx}.{e_idx}."
                
                # Standard SxxExx text episode number format
                ep_onscreen = ET.SubElement(prog_elem, "episode-num", {"system": "onscreen"})
                ep_onscreen.text = f"S{slot['season_number']:02d}E{slot['episode_number']:02d}"

    # Pretty print XML
    rough_string = ET.tostring(tv_elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
