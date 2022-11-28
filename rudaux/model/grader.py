from pydantic import BaseModel


class Grader(BaseModel):
    name: str
    info: dict
    status: int
    skip: bool
