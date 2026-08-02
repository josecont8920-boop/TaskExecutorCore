from typing import List, Optional
import uuid
import json
import os
from .profile import Profile
from .session import Session
from config.settings import settings

class ProfileManager:
    def __init__(self):
        self.storage_path = settings.PROFILES_STORAGE_PATH
        os.makedirs(self.storage_path, exist_ok=True)

    def create_profile(self, name: str, proxy: Optional[str] = None, user_agent: Optional[str] = None) -> Profile:
        profile_id = str(uuid.uuid4())
        profile = Profile(
            id=profile_id,
            name=name,
            proxy=proxy,
            user_agent=user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."
        )
        self._save_profile(profile)
        return profile

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        path = os.path.join(self.storage_path, f"{profile_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            data = json.load(f)
        return Profile(**data)

    def start_session(self, profile_id: str) -> Optional[Session]:
        profile = self.get_profile(profile_id)
        if not profile:
            return None
        driver = f"MockDriver_for_{profile_id}"
        return Session(profile=profile, driver=driver)

    def _save_profile(self, profile: Profile):
        path = os.path.join(self.storage_path, f"{profile.id}.json")
        with open(path, 'w') as f:
            json.dump(profile.model_dump(), f, indent=2)

    def list_profiles(self) -> List[str]:
        return [f.replace('.json', '') for f in os.listdir(self.storage_path) if f.endswith('.json')]
