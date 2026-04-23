from enum import StrEnum, auto


class CallStage(StrEnum):
    GREETING = auto()
    DISCOVERY = auto()
    QUALIFICATION = auto()
    OBJECTION_HANDLING = auto()
    BOOKING = auto()
    CLOSING = auto()
    ENDED = auto()


class TaskType(StrEnum):
    CONVERSATION = auto()
    SUMMARIZATION = auto()
    CLASSIFICATION = auto()
    LEAD_SCORING = auto()
    EMAIL_DRAFT = auto()


class Intent(StrEnum):
    QUALIFY_LEAD = auto()
    BOOK_MEETING = auto()
    HANDLE_OBJECTION = auto()
    CLOSE_CALL = auto()
    REQUEST_INFO = auto()
    SMALL_TALK = auto()


class LeadScore(StrEnum):
    HOT = auto()
    WARM = auto()
    COLD = auto()
    UNQUALIFIED = auto()
