import requests
from typing import List, Dict, Any, Optional
from app.database import get_setting

class JellyfinClient:
    def __init__(self, server_url: Optional[str] = None, api_key: Optional[str] = None):
        url = server_url if server_url is not None else get_setting("jellyfin_url", "")
        key = api_key if api_key is not None else get_setting("jellyfin_api_key", "")
        self.server_url = url.strip().rstrip("/")
        self.api_key = key.strip()

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/json",
            "User-Agent": "ChannelBuilder/1.0.0"
        }
        if self.api_key:
            headers["X-Emby-Token"] = self.api_key
            headers["Authorization"] = f'MediaBrowser Client="ChannelBuilder", Device="Server", DeviceId="channel-builder", Version="1.0.0", Token="{self.api_key}"'
        return headers

    def _params(self, extra_params: Optional[dict] = None) -> dict:
        p = {}
        if self.api_key:
            p["api_key"] = self.api_key
            p["api-key"] = self.api_key
        if extra_params:
            p.update(extra_params)
        return p

    def is_configured(self) -> bool:
        return bool(self.server_url and self.api_key)

    def test_connection(self) -> dict:
        if not self.is_configured():
            return {"success": False, "message": "Server URL and API Key are required."}
        
        # Test 1: Fetch System Info
        try:
            url = f"{self.server_url}/System/Info"
            resp = requests.get(url, headers=self._headers(), params=self._params(), timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                server_name = data.get("ServerName", "Jellyfin")
                version = data.get("Version", "Unknown")
                
                # Test 2: Verify API key with an authenticated query (/Items?Limit=1)
                auth_test_url = f"{self.server_url}/Items"
                auth_resp = requests.get(auth_test_url, headers=self._headers(), params=self._params({"Limit": 1}), timeout=10)
                
                if auth_resp.status_code == 200:
                    return {"success": True, "server_name": server_name, "version": version}
                elif auth_resp.status_code in (401, 403):
                    return {"success": False, "message": f"Server reached ({server_name}), but API Key was rejected (HTTP {auth_resp.status_code}). Check Dashboard -> Settings -> API Keys."}
                else:
                    return {"success": False, "message": f"Server reached ({server_name}), but item auth check returned HTTP {auth_resp.status_code}."}
            
            elif resp.status_code in (401, 403):
                return {"success": False, "message": f"Invalid API Key (HTTP {resp.status_code}). Please generate a key under Jellyfin Dashboard -> Settings -> API Keys."}
            elif resp.status_code == 404:
                return {"success": False, "message": f"Endpoint not found (HTTP 404). Check if server URL '{self.server_url}' is correct and includes port/subpath."}
            else:
                return {"success": False, "message": f"Jellyfin returned HTTP {resp.status_code}: {resp.text[:100]}"}
                
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Failed to connect to Jellyfin at '{self.server_url}': {str(e)}"}

    def get_libraries(self) -> List[Dict[str, Any]]:
        """Fetch Jellyfin media libraries (UserViews)"""
        if not self.is_configured():
            return []
        try:
            url = f"{self.server_url}/Items"
            params = self._params({
                "IncludeItemTypes": "CollectionFolder",
                "Recursive": "true"
            })
            resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("Items", [])
                return [{"id": item["Id"], "name": item["Name"], "collection_type": item.get("CollectionType")} for item in items]
            return []
        except Exception:
            return []

    def get_shows_and_movies(self, library_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch Series or Movies available in Jellyfin"""
        if not self.is_configured():
            return []
        try:
            url = f"{self.server_url}/Items"
            extra = {
                "IncludeItemTypes": "Series,Movie",
                "Recursive": "true",
                "Fields": "PrimaryImageAspectRatio,Overview,RunTimeTicks,SeriesName",
                "SortBy": "SortName"
            }
            if library_id:
                extra["ParentId"] = library_id

            resp = requests.get(url, headers=self._headers(), params=self._params(extra), timeout=15)
            if resp.status_code == 200:
                items = resp.json().get("Items", [])
                result = []
                for item in items:
                    item_type = item.get("Type") # 'Series' or 'Movie'
                    duration_sec = (item.get("RunTimeTicks") or 0) / 10_000_000
                    img_url = f"{self.server_url}/Items/{item['Id']}/Images/Primary?api_key={self.api_key}" if item.get("ImageTags", {}).get("Primary") else None
                    result.append({
                        "id": item["Id"],
                        "name": item.get("Name"),
                        "type": item_type,
                        "overview": item.get("Overview", ""),
                        "duration_seconds": duration_sec,
                        "image_url": img_url
                    })
                return result
            return []
        except Exception as e:
            print(f"Error fetching shows and movies: {e}")
            return []

    def get_episodes_for_series(self, series_id: str) -> List[Dict[str, Any]]:
        """Fetch all playable episodes for a given TV series ID"""
        if not self.is_configured():
            return []
        try:
            url = f"{self.server_url}/Shows/{series_id}/Episodes"
            extra = {
                "Fields": "Overview,RunTimeTicks,SeriesName,IndexNumber,ParentIndexNumber,PrimaryImageAspectRatio",
                "SortBy": "ParentIndexNumber,IndexNumber"
            }
            resp = requests.get(url, headers=self._headers(), params=self._params(extra), timeout=15)
            if resp.status_code == 200:
                items = resp.json().get("Items", [])
                episodes = []
                for item in items:
                    ticks = item.get("RunTimeTicks", 0)
                    duration_sec = ticks / 10_000_000 if ticks else 1800
                    season_num = item.get("ParentIndexNumber", 1)
                    ep_num = item.get("IndexNumber", 1)
                    series_name = item.get("SeriesName", "TV Show")
                    ep_name = item.get("Name", f"Episode {ep_num}")
                    
                    episodes.append({
                        "id": item["Id"],
                        "type": "Episode",
                        "series_id": series_id,
                        "series_name": series_name,
                        "title": f"{series_name} S{season_num:02d}E{ep_num:02d} - {ep_name}",
                        "short_title": ep_name,
                        "season_number": season_num,
                        "episode_number": ep_num,
                        "overview": item.get("Overview", ""),
                        "duration_seconds": duration_sec,
                        "stream_url": f"{self.server_url}/Videos/{item['Id']}/stream?static=true&api_key={self.api_key}",
                        "image_url": f"{self.server_url}/Items/{item['Id']}/Images/Primary?api_key={self.api_key}" if item.get("ImageTags", {}).get("Primary") else None
                    })
                return episodes
            return []
        except Exception as e:
            print(f"Error fetching episodes: {e}")
            return []

    def get_movie_item(self, movie_id: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata for a single movie"""
        if not self.is_configured():
            return None
        try:
            url = f"{self.server_url}/Items/{movie_id}"
            resp = requests.get(url, headers=self._headers(), params=self._params({"Fields": "Overview,RunTimeTicks"}), timeout=10)
            if resp.status_code == 200:
                item = resp.json()
                ticks = item.get("RunTimeTicks", 0)
                duration_sec = ticks / 10_000_000 if ticks else 5400
                return {
                    "id": item["Id"],
                    "type": "Movie",
                    "title": item.get("Name", "Movie"),
                    "overview": item.get("Overview", ""),
                    "duration_seconds": duration_sec,
                    "stream_url": f"{self.server_url}/Videos/{item['Id']}/stream?static=true&api_key={self.api_key}",
                    "image_url": f"{self.server_url}/Items/{item['Id']}/Images/Primary?api_key={self.api_key}" if item.get("ImageTags", {}).get("Primary") else None
                }
            return None
        except Exception as e:
            print(f"Error fetching movie item: {e}")
            return None
