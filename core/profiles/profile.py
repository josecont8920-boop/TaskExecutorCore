from pydantic import BaseModel
from typing import Optional

class Profile(BaseModel):
    id: str
    name: str
    proxy: Optional[str] = None
    user_agent: str
