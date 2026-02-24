from django.db.models import Count
from .models import (
    WeeklyReport,
    ReportContent,
    Comment,
    Supervisor,
    SubmissionDeadline,
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

def get_effective_deadline(supervisor):
    """
    Returns the latest effective deadline for a supervisor.
    Prefers an approved extension when present; otherwise uses the base due datetime.
    """
    deadline = SubmissionDeadline.objects.filter(
        supervisor=supervisor
    ).order_by("-reporting_week__year", "-reporting_week__week_number").first()

    if not deadline:
        return None

    return deadline.extended_datetime or deadline.due_datetime
