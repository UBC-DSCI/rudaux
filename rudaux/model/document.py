from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class Document(BaseModel):
    info: Any
    data: Any
