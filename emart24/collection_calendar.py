"""Calendar primitives for the new collector; does not activate scheduling."""
from datetime import datetime, time, timedelta

from .core import KST


def collection_dates(start, through):
    """An explicit start prevents guessing how far historical recovery reaches."""
    if start > through:
        return []
    return [start + timedelta(days=n) for n in range((through-start).days+1)
            if (start+timedelta(days=n)).weekday() != 6]


def polling_slots(day):
    if day.weekday() == 6:
        return []
    first=datetime.combine(day,time(10,40),KST)
    return [first+timedelta(minutes=n) for n in (0,5,10,15,20,25,30)]
