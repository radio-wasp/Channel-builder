import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, LOCAL_COMMERCIALS_DIR
from app.database import (
    init_db, get_setting, set_setting, get_channels, get_channel,
    create_channel, update_channel, delete_channel
)
from app.jellyfin import JellyfinClient
from app.youtube import download_youtube_commercials, scan_local_commercials
from app.scheduler import generate_channel_schedule, get_channel_schedule, get_currently_playing_slot
from app.epg import generate_epg_xml
from app.m3u import generate_m3u_playlist
from app.streamer import generate_mpegts_stream

app = FastAPI(title="ChannelBuilder", version="1.0.0")

# Setup templates
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@app.on_event("startup")
def startup_event():
    init_db()

# Helper to get base host URL from request
def get_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")

# Background Commercial Download Handler
def process_channel_commercials(channel_id: int):
    ch = get_channel(channel_id)
    if not ch:
        return
    src_type = ch.get("commercial_source_type")
    src_val = ch.get("commercial_source_value")
    
    if src_type == "youtube" and src_val:
        download_youtube_commercials(channel_id, src_val)
    elif src_type == "local" and src_val:
        scan_local_commercials(channel_id, src_val)
        
    # Refresh schedule after commercials are indexed
    generate_channel_schedule(channel_id)

# Routes

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    jellyfin = JellyfinClient()
    jellyfin_conn = jellyfin.test_connection()
    channels = get_channels()
    return templates.TemplateResponse(request=request, name="index.html", context={
        "active_page": "dashboard",
        "jellyfin_connected": jellyfin_conn["success"],
        "channels": channels,
        "host_url": get_base_url(request)
    })

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "active_page": "settings",
        "jellyfin_url": get_setting("jellyfin_url", ""),
        "jellyfin_api_key": get_setting("jellyfin_api_key", ""),
        "local_commercials_dir": str(LOCAL_COMMERCIALS_DIR)
    })

@app.post("/settings", response_class=HTMLResponse)
def save_settings(
    request: Request,
    jellyfin_url: str = Form(...),
    jellyfin_api_key: str = Form(...)
):
    set_setting("jellyfin_url", jellyfin_url.strip())
    set_setting("jellyfin_api_key", jellyfin_api_key.strip())
    
    client = JellyfinClient(jellyfin_url, jellyfin_api_key)
    res = client.test_connection()
    
    msg = f"Connected to Jellyfin: {res.get('server_name')} (v{res.get('version')})" if res["success"] else f"Connection Error: {res.get('message')}"
    
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "active_page": "settings",
        "jellyfin_url": jellyfin_url,
        "jellyfin_api_key": jellyfin_api_key,
        "local_commercials_dir": str(LOCAL_COMMERCIALS_DIR),
        "message": msg,
        "success": res["success"]
    })

@app.get("/channels", response_class=HTMLResponse)
def channels_page(request: Request):
    channels = get_channels()
    return templates.TemplateResponse(request=request, name="channels.html", context={
        "active_page": "channels",
        "channels": channels
    })

@app.get("/channels/new", response_class=HTMLResponse)
def new_channel_page(request: Request):
    jellyfin = JellyfinClient()
    items = jellyfin.get_shows_and_movies()
    existing_channels = get_channels()
    next_num = max([c["number"] for c in existing_channels], default=0) + 1
    
    return templates.TemplateResponse(request=request, name="channel_form.html", context={
        "active_page": "channels",
        "edit_mode": False,
        "jellyfin_items": items,
        "next_number": next_num,
        "channel": None
    })

@app.post("/channels/new")
def create_channel_handler(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    number: int = Form(...),
    logo_url: str = Form(""),
    content_type: str = Form(...),
    selected_items: List[str] = Form([]),
    commercial_source_type: str = Form("youtube"),
    commercial_source_value: str = Form(...),
    break_duration_seconds: int = Form(120),
    shuffle_mode: Optional[str] = Form(None)
):
    ch_id = create_channel(
        name=name.strip(),
        number=number,
        logo_url=logo_url.strip(),
        content_type=content_type,
        selected_items=selected_items,
        commercial_source_type=commercial_source_type,
        commercial_source_value=commercial_source_value.strip(),
        break_duration_seconds=break_duration_seconds,
        shuffle_mode=bool(shuffle_mode)
    )
    
    # Generate schedule and trigger background commercial download/sync
    generate_channel_schedule(ch_id)
    background_tasks.add_task(process_channel_commercials, ch_id)
    
    return RedirectResponse(url=f"/channels/{ch_id}", status_code=303)

@app.get("/channels/{channel_id}", response_class=HTMLResponse)
def channel_detail(request: Request, channel_id: int):
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    schedule = get_channel_schedule(channel_id)
    current_slot = get_currently_playing_slot(channel_id)
    
    return templates.TemplateResponse(request=request, name="channel_detail.html", context={
        "active_page": "channels",
        "channel": ch,
        "schedule": schedule,
        "current_slot": current_slot
    })

@app.get("/channels/{channel_id}/edit", response_class=HTMLResponse)
def edit_channel_page(request: Request, channel_id: int):
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    jellyfin = JellyfinClient()
    items = jellyfin.get_shows_and_movies()
    
    return templates.TemplateResponse(request=request, name="channel_form.html", context={
        "active_page": "channels",
        "edit_mode": True,
        "jellyfin_items": items,
        "channel": ch
    })

@app.post("/channels/{channel_id}/edit")
def edit_channel_handler(
    channel_id: int,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    number: int = Form(...),
    logo_url: str = Form(""),
    content_type: str = Form(...),
    selected_items: List[str] = Form([]),
    commercial_source_type: str = Form("youtube"),
    commercial_source_value: str = Form(...),
    break_duration_seconds: int = Form(120),
    shuffle_mode: Optional[str] = Form(None)
):
    update_channel(
        channel_id=channel_id,
        name=name.strip(),
        number=number,
        logo_url=logo_url.strip(),
        content_type=content_type,
        selected_items=selected_items,
        commercial_source_type=commercial_source_type,
        commercial_source_value=commercial_source_value.strip(),
        break_duration_seconds=break_duration_seconds,
        shuffle_mode=bool(shuffle_mode)
    )
    
    generate_channel_schedule(channel_id)
    background_tasks.add_task(process_channel_commercials, channel_id)
    
    return RedirectResponse(url=f"/channels/{channel_id}", status_code=303)

@app.post("/channels/{channel_id}/delete")
def delete_channel_handler(channel_id: int):
    delete_channel(channel_id)
    return RedirectResponse(url="/channels", status_code=303)

@app.post("/channels/{channel_id}/sync_commercials")
def sync_commercials_handler(channel_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_channel_commercials, channel_id)
    return RedirectResponse(url=f"/channels/{channel_id}", status_code=303)

@app.post("/channels/{channel_id}/refresh_schedule")
def refresh_schedule_handler(channel_id: int):
    generate_channel_schedule(channel_id)
    return RedirectResponse(url=f"/channels/{channel_id}", status_code=303)

# IPTV Ingest Endpoints for Dispatcharr / Jellyfin Live TV

@app.get("/playlist.m3u")
def get_m3u(request: Request):
    m3u_content = generate_m3u_playlist(get_base_url(request))
    return Response(content=m3u_content, media_type="audio/x-mpegurl")

@app.get("/epg.xml")
def get_epg(request: Request):
    epg_content = generate_epg_xml(get_base_url(request))
    return Response(content=epg_content, media_type="application/xml")

# Stream Output Endpoints
@app.get("/stream/{channel_id}/live.ts")
def stream_mpegts(channel_id: int):
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    return StreamingResponse(
        generate_mpegts_stream(channel_id),
        media_type="video/mp2t"
    )

@app.get("/stream/{channel_id}/index.m3u8")
def stream_hls(channel_id: int):
    # Direct alias to live TS stream endpoint for IPTV clients requesting .m3u8
    return RedirectResponse(url=f"/stream/{channel_id}/live.ts")
