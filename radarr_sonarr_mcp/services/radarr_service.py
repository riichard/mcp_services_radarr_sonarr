"""Service for interacting with Radarr API."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import requests
from ..config import RadarrConfig


@dataclass
class Movie:
    """Movie data class."""
    id: int
    title: str
    year: int
    overview: str
    has_file: bool
    status: str
    tags: List[int] = None
    genres: List[str] = None
    data: Dict[str, Any] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Movie':
        """Create a Movie object from a dictionary."""
        return cls(
            id=data['id'],
            title=data['title'],
            year=data.get('year', 0),
            overview=data.get('overview', ''),
            has_file=data.get('hasFile', False),
            status=data.get('status', ''),
            tags=data.get('tags', []),
            genres=data.get('genres', []),
            data=data
        )


class RadarrService:
    """Service for interacting with Radarr API."""
    
    def __init__(self, config: RadarrConfig):
        """Initialize the Radarr service with configuration."""
        self.config = config
    
    def get_all_movies(self) -> List[Movie]:
        """Fetch all movies from Radarr."""
        try:
            response = requests.get(
                f"{self.config.base_url}/movie",
                params={"apikey": self.config.api_key},
                timeout=30
            )
            response.raise_for_status()
            
            movies = []
            for movie_data in response.json():
                movies.append(Movie.from_dict(movie_data))
            
            return movies
        except requests.RequestException as e:
            import logging
            logging.error(f"Error fetching movies from Radarr: {e}")
            raise Exception(f"Failed to fetch movies from Radarr: {e}")
    
    def lookup_movie(self, term: str) -> List[Movie]:
        """Look up movies by search term."""
        try:
            response = requests.get(
                f"{self.config.base_url}/movie/lookup",
                params={"term": term, "apikey": self.config.api_key},
                timeout=30
            )
            response.raise_for_status()
            
            movies = []
            for movie_data in response.json():
                movies.append(Movie.from_dict(movie_data))
            
            return movies
        except requests.RequestException as e:
            import logging
            logging.error(f"Error looking up movie in Radarr: {e}")
            raise Exception(f"Failed to lookup movie in Radarr: {e}")
    
    def get_movie_file(self, movie_id: int) -> Dict[str, Any]:
        """Get the file information for a movie."""
        try:
            response = requests.get(
                f"{self.config.base_url}/moviefile",
                params={"movieId": movie_id, "apikey": self.config.api_key},
                timeout=30
            )
            response.raise_for_status()
            
            return response.json()
        except requests.RequestException as e:
            import logging
            logging.error(f"Error fetching movie file for ID {movie_id}: {e}")
            raise Exception(f"Failed to fetch movie file: {e}")

    def is_movie_watched(self, movie: Movie) -> bool:
        """Check if a movie is watched based on tags."""
        # This is an assumption - actual implementation may vary based on how
        # watched status is tracked in your Radarr setup
        return movie.data.get('movieFile', {}).get('mediaInfo', {}).get('watched', False)

    def is_movie_in_watchlist(self, movie: Movie) -> bool:
        """Check if a movie is in the watchlist based on tags."""
        # This is an assumption - implementation may vary
        # Assuming 'watchlist' tag with ID 1 (adjust as needed)
        return 1 in (movie.tags or [])

    def get_quality_profiles(self) -> dict:
        """Fetch quality profiles from Radarr."""
        response = requests.get(
            f"{self.config.base_url}/qualityprofile",
            params={"apikey": self.config.api_key},
            timeout=30,
        )
        response.raise_for_status()
        profiles = response.json()
        return {
            "count": len(profiles),
            "profiles": [{"id": p["id"], "name": p["name"]} for p in profiles],
        }

    def get_root_folders(self) -> dict:
        """Fetch root folders from Radarr."""
        response = requests.get(
            f"{self.config.base_url}/rootfolder",
            params={"apikey": self.config.api_key},
            timeout=30,
        )
        response.raise_for_status()
        folders = response.json()
        return {
            "count": len(folders),
            "folders": [{"id": f["id"], "path": f["path"], "freeSpace": f.get("freeSpace")} for f in folders],
        }

    def add_movie(
        self,
        tmdb_id: int,
        quality_profile_id: int,
        root_folder_path: str = "/mnt/media/movies",
        search_on_add: bool = True,
        monitored: bool = True,
    ) -> dict:
        """Add a movie to Radarr by TMDB ID."""
        results = self.lookup_movie(f"tmdb:{tmdb_id}")
        if not results:
            raise Exception(f"No movie found with TMDB ID {tmdb_id}")
        movie = results[0]

        payload = {
            "tmdbId": tmdb_id,
            "title": movie.title,
            "year": movie.year,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {
                "searchForMovie": search_on_add,
            },
        }
        response = requests.post(
            f"{self.config.base_url}/movie",
            params={"apikey": self.config.api_key},
            json=payload,
            timeout=30,
        )
        if response.status_code == 400:
            err = response.json()
            raise Exception(f"Radarr error: {err}")
        response.raise_for_status()
        added = response.json()
        return {"id": added.get("id"), "title": added.get("title"), "status": "added"}

