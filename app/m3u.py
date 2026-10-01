from app.database import get_channels

def generate_m3u_playlist(host_base_url: str) -> str:
    """
    Generates standard M3U IPTV playlist format for Dispatcharr / Jellyfin / IPTV clients.
    """
    host_base_url = host_base_url.rstrip("/")
    epg_url = f"{host_base_url}/epg.xml"
    
    lines = [f'#EXTM3U url-tvg="{epg_url}"']
    
    channels = get_channels()
    for ch in channels:
        ch_id = f"channel.{ch['id']}"
        logo_attr = f' tvg-logo="{ch["logo_url"]}"' if ch.get("logo_url") else ""
        
        extinf = f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{ch["name"]}" tvg-chno="{ch["number"]}"{logo_attr} group-title="ChannelBuilder",{ch["name"]}'
        stream_url = f'{host_base_url}/stream/{ch["id"]}/index.m3u8'
        
        lines.append(extinf)
        lines.append(stream_url)
        
    return "\n".join(lines)
