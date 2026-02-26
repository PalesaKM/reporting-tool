from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .helpers import ensure_reporting_week, seed_weekly_deadlines_from_previous


class EnsureReportingWeekMiddleware:
    """
    Ensures the current ISO reporting week exists.
    This runs once per process per calendar day and creates the current
    ReportingWeek record on the first request after rollover (including Monday).
    """

    _last_checked_date = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        today = timezone.localdate()
        if EnsureReportingWeekMiddleware._last_checked_date != today:
            iso = today.isocalendar()
            try:
                reporting_week = ensure_reporting_week(iso.week, iso.year)
                seed_weekly_deadlines_from_previous(reporting_week)
            except (OperationalError, ProgrammingError):
                # DB might not be ready yet (startup/migrations). Skip silently.
                pass
            EnsureReportingWeekMiddleware._last_checked_date = today

        return self.get_response(request)
