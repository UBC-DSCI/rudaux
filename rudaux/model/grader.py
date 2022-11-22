from pydantic import BaseModel


class Grader(BaseModel):
    name: str
    info: dict
