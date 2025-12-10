# The date format required by the HTML5 datepicker.
import datetime

DATE_FORMAT = '%Y-%m-%d'


def to_datepicker(dt):
    """Convert a datetime to a string suitable for the HTML5 datepicker."""
    if dt is None:
        return ''
    return dt.strftime(DATE_FORMAT)


def from_datepicker(date_str):
    """Convert a string from the HTML5 datepicker format to a native datetime."""
    return datetime.datetime.strptime(date_str, DATE_FORMAT)


def format_duration(start_date, end_date):
    """Return the difference between two actual calendar dates in years, months and days.
    - Using a timedelta here would not be accurate, as it's disconnected from real dates, and we'd
    have to use average month and year lengths for the conversions.
    """
    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day
    if days < 0:
        months -= 1
        prev_month = (end_date.month - 1) or 12
        prev_year = end_date.year if end_date.month > 1 else end_date.year - 1
        last_month_day = (
            datetime.date(prev_year, prev_month + 1, 1) - datetime.date(prev_year, prev_month, 1)
        ).days
        days += last_month_day
    if months < 0:
        years -= 1
        months += 12
    # Format string that only includes non-zero elements.
    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    return ', '.join(parts)

