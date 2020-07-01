from enum import Enum


class IssueState:
    TEST = 'Ready for Test'
    MERGE = 'Ready for Merge'
    CLOSED = 'Closed'
    IN_PROGRESS = 'In Progress'


class ReviewState(Enum):
    OPENED = 1
    CLOSED = 2


class LabelColor(Enum):
    GREEN = 0
    RED = 2


class ParticipantState(Enum):
    UNREAD = 1
    READ = 2
    ACCEPTED = 3
    REJECTED = 4


class ParticipantRole(Enum):
    REVIEWER = 2
