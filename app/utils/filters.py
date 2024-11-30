from datetime import datetime

def format_datetime(value):
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime('%B %d, %Y %I:%M %p')
    except (ValueError, TypeError):
        return value