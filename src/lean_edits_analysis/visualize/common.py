from datetime import datetime

from pydantic import BaseModel


class ChangeEventInfo(BaseModel):
    characters_added: int
    characters_removed: int
    time: datetime
