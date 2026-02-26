from datetime import date, datetime, timedelta

from django.db.models import Count
from django.utils import timezone
from .models import (
    WeeklyReport,
    ReportContent,
    Comment,
    Supervisor,
    SubmissionDeadline,
    ReportingWeek,
)

# -------------------------------
# 1. FETCH SINGLE REPORT
# -------------------------------
def get_report_by_pk(report_pk, supervisor_profile):
    """
    Fetch a single WeeklyReport for the supervisor, or return None if not found.
    """
    try:
        return WeeklyReport.objects.get(pk=report_pk, supervisor=supervisor_profile)
    except WeeklyReport.DoesNotExist:
        return None

# -------------------------------
# 2. CREATE NEW REPORT
# -------------------------------
def create_weekly_report(supervisor_profile):
    """
    Initialize a new WeeklyReport instance for the supervisor.
    """
    return WeeklyReport(supervisor=supervisor_profile)

# -------------------------------
# 3. FETCH ALL REPORTS FOR SUPERVISOR
# -------------------------------
def get_weekly_reports_for_supervisor(supervisor_profile):
    """
    Return all WeeklyReports for a given supervisor, ordered by week_number descending.
    """
    return WeeklyReport.objects.filter(supervisor=supervisor_profile).order_by('-week_number')

# -------------------------------
# 4. FETCH PENDING REPORTS
# -------------------------------
def get_pending_reports_for_supervisor(supervisor_profile):
    """
    Return all WeeklyReports that are pending approval (status='Pending').
    """
    return WeeklyReport.objects.filter(supervisor=supervisor_profile, status='Pending').order_by('-week_number')

# -------------------------------
# 5. REPORT STATISTICS
# -------------------------------
def get_report_statistics(supervisor_profile):
    """
    Return counts of reports grouped by status for this supervisor.
    Example output: {'Pending': 3, 'Approved': 5, 'Rejected': 1}
    """
    queryset = WeeklyReport.objects.filter(supervisor=supervisor_profile)
    stats = queryset.values('status').annotate(count=Count('id'))
    # Convert queryset to dictionary
    return {item['status']: item['count'] for item in stats}

def get_submission_deadline_for_supervisor(supervisor, week_number=None, year=None):
    """
    Return a SubmissionDeadline for a supervisor scoped to a specific ISO week/year.
    Falls back to the latest configured deadline when no scoped record exists.
    """
    if week_number is None or year is None:
        local_now = timezone.localtime(timezone.now())
        iso = local_now.isocalendar()
        week_number = week_number or iso.week
        year = year or iso.year

    scoped = SubmissionDeadline.objects.filter(
        supervisor=supervisor,
        reporting_week__week_number=week_number,
        reporting_week__year=year,
    ).order_by("-id").first()

    if scoped:
        return scoped

    return SubmissionDeadline.objects.filter(
        supervisor=supervisor
    ).order_by("-reporting_week__year", "-reporting_week__week_number", "-id").first()


def ensure_reporting_week(week_number, year):
    """
    Ensure a ReportingWeek exists for an ISO week/year pair.
    """
    start = date.fromisocalendar(year, week_number, 1)
    end = date.fromisocalendar(year, week_number, 7)
    reporting_week, _ = ReportingWeek.objects.get_or_create(
        week_number=week_number,
        year=year,
        defaults={"start_date": start, "end_date": end},
    )
    return reporting_week


def seed_weekly_deadlines_from_previous(reporting_week):
    """
    For each supervisor, create a SubmissionDeadline for `reporting_week` if missing,
    copying weekday/time from that supervisor's most recent deadline.
    """
    created_count = 0

    for supervisor in Supervisor.objects.all():
        existing = SubmissionDeadline.objects.filter(
            supervisor=supervisor,
            reporting_week=reporting_week,
        ).first()
        if existing:
            continue

        source = (
            SubmissionDeadline.objects.filter(supervisor=supervisor)
            .exclude(reporting_week=reporting_week)
            .order_by("-reporting_week__year", "-reporting_week__week_number", "-due_datetime")
            .first()
        )
        if not source:
            continue

        source_due = source.due_datetime
        if timezone.is_aware(source_due):
            source_due = timezone.localtime(source_due)
        else:
            source_due = timezone.make_aware(source_due, timezone.get_current_timezone())

        if source.reporting_week_id and source.reporting_week.start_date:
            day_shift = (reporting_week.start_date - source.reporting_week.start_date).days
            new_due = source_due + timedelta(days=day_shift)
        else:
            offset = source_due.isoweekday() - 1  # Monday=0 ... Sunday=6
            target_date = reporting_week.start_date + timedelta(days=offset)
            naive_target = datetime.combine(
                target_date, source_due.timetz().replace(tzinfo=None)
            )
            new_due = timezone.make_aware(naive_target, timezone.get_current_timezone())

        SubmissionDeadline.objects.create(
            supervisor=supervisor,
            reporting_week=reporting_week,
            due_datetime=new_due,
            extended_datetime=None,
        )
        created_count += 1

    return created_count


def get_effective_deadline(supervisor, week_number=None, year=None):
    """
    Returns the effective deadline for a supervisor for an ISO week/year.
    Prefers an approved extension when present; otherwise uses the base due datetime.
    """
    deadline = get_submission_deadline_for_supervisor(
        supervisor, week_number=week_number, year=year
    )

    if not deadline:
        return None

    return deadline.extended_datetime or deadline.due_datetime
