from datetime import datetime, timedelta

def format_datetime(value):
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime('%B %d, %Y %I:%M %p')
    except (ValueError, TypeError):
        return value

def is_today(value):
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(value)
        today = datetime.now().date()
        return dt.date() == today
    except (ValueError, TypeError):
        return False

def within_days(value, days):
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(value)
        cutoff = datetime.now() - timedelta(days=days)
        return dt > cutoff
    except (ValueError, TypeError):
        return False