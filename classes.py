import typing as tp
from datetime import datetime


# Lesson object with corresponding attributes
class Lesson:
    def __init__(self) -> None:
        self.title: str  # lesson name
        self.type: str  # type e.g. lecture, lab, etc.
        self.start_time: tp.Optional[datetime] = None  # datetime object
        self.end_time: tp.Optional[datetime] = None  # datetime object
        self.course_link: str = ''  # moodle link
        self.location: str = ''  # address or online
