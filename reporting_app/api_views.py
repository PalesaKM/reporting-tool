from datetime import timedelta
from django.utils import timezone
from django.utils.timezone import make_aware
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status

from .auth import APIKeyAuthentication
from .models import WeeklyReport, DailyReport, SubmissionDeadline, Comment, DailyReportComment


def isoformat(dt):
    return dt.isoformat() if dt else None


@api_view(['GET', 'POST'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([])
def last_30_days_reports(request):
    today = timezone.now()
    start_date = today - timedelta(days=30)

    # Filters
    report_type_filter = request.query_params.get('report_type', None)  # "Daily" or "Weekly"
    employee_email_filter = request.query_params.get('employee_email', None)

    # Pagination
    try:
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
    except ValueError:
        return Response({"error": "page and page_size must be integers"}, status=status.HTTP_400_BAD_REQUEST)

    offset = (page - 1) * page_size
    limit = offset + page_size

    results = []

    # =========================
    # WEEKLY REPORTS
    # =========================
    if report_type_filter in [None, "Weekly"]:
        weekly_qs = WeeklyReport.objects.filter(
            submission_timestamp__gte=start_date
        ).select_related("supervisor").prefetch_related("supervisor__managers").order_by("-submission_timestamp")

        if employee_email_filter:
            weekly_qs = weekly_qs.filter(supervisor__email=employee_email_filter)

        total_weekly = weekly_qs.count()
        weekly_reports = weekly_qs[offset:limit]

        for report in weekly_reports:
            supervisor = report.supervisor

            # Get all managers linked to supervisor
            approvers = supervisor.managers.all()
            approver_names = [f"{m.first_name} {m.last_name}" for m in approvers]
            approver_emails = [m.email for m in approvers]

            # Deadline & late flag
            deadline = SubmissionDeadline.objects.filter(
                supervisor=supervisor,
                reporting_week__week_number=report.week_number
            ).first()
            due_datetime = deadline.extended_datetime or deadline.due_datetime if deadline else None
            is_late = report.submission_timestamp > due_datetime if due_datetime else False

            # Comments
            comments_qs = Comment.objects.filter(report=report)
            comments_list = [
                {
                    "comment": c.comment_text,
                    "timestamp": isoformat(c.time_stamp),
                    "commented_by": f"{c.manager.first_name} {c.manager.last_name}",
                }
                for c in comments_qs
            ]

            results.append({
                "report_type": "Weekly",
                "report_id": report.id,
                "employee_name": f"{supervisor.first_name} {supervisor.last_name}",
                "employee_email": supervisor.email,
                "status": report.status,
                "submission_timestamp": isoformat(report.submission_timestamp),
                "due_datetime": isoformat(due_datetime),
                "is_late": is_late,
                "is_resubmission": report.status == "Rework",
                "approver_name": approver_names,
                "approver_email": approver_emails,
                "comments": comments_list,
            })

    # =========================
    # DAILY REPORTS
    # =========================
    if report_type_filter in [None, "Daily"]:
        daily_qs = DailyReport.objects.filter(
            submission_timestamp__gte=start_date
        ).select_related("supervisor").prefetch_related("supervisor__managers").order_by("-submission_timestamp")

        if employee_email_filter:
            daily_qs = daily_qs.filter(supervisor__email=employee_email_filter)

        total_daily = daily_qs.count()
        daily_reports = daily_qs[offset:limit]

        for report in daily_reports:
            supervisor = report.supervisor

            approvers = supervisor.managers.all() if supervisor else []
            approver_names = [f"{m.first_name} {m.last_name}" for m in approvers]
            approver_emails = [m.email for m in approvers]

            submission_time = report.submission_timestamp
            report_date = submission_time.date()
            # Daily deadline = 4PM on submission day
            deadline_time = make_aware(
                timezone.datetime(report_date.year, report_date.month, report_date.day, 16, 0, 0)
            )
            is_late = submission_time > deadline_time

            comments_qs = DailyReportComment.objects.filter(report=report)
            comments_list = [
                {
                    "comment": c.comment_text,
                    "timestamp": isoformat(c.time_stamp),
                    "commented_by": f"{c.manager.first_name} {c.manager.last_name}",
                }
                for c in comments_qs
            ]

            results.append({
                "report_type": "Daily",
                "report_id": report.id,
                "employee_name": f"{supervisor.first_name} {supervisor.last_name}" if supervisor else None,
                "employee_email": supervisor.email if supervisor else None,
                "status": report.status,
                "submission_timestamp": isoformat(submission_time),
                "due_datetime": isoformat(deadline_time),
                "is_late": is_late,
                "is_resubmission": report.status == "Rework",
                "approver_name": approver_names,
                "approver_email": approver_emails,
                "comments": comments_list,
            })

    total_reports = (total_weekly if report_type_filter in [None, "Weekly"] else 0) + \
                    (total_daily if report_type_filter in [None, "Daily"] else 0)

    return Response({
        "page": page,
        "page_size": page_size,
        "total_reports": total_reports,
        "reports": results
    }, status=status.HTTP_200_OK)