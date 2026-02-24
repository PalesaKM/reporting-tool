from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from .models import ReportSubmission

def last_30_days_reports(request):
    today = timezone.now().date()
    start_date = today - timedelta(days=30)

    reports = ReportSubmission.objects.filter(
        created_at__date__gte=start_date
    ).select_related("employee", "approver")

    data = []

    for report in reports:
        data.append({
            "employee_name": report.employee.get_full_name(),
            "employee_email": report.employee.email,
            "status": report.status,
            "due_date": report.due_date,
            "submission_date": report.submission_date,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
            "approver_name": report.approver.get_full_name() if report.approver else None,
            "approver_email": report.approver.email if report.approver else None,
            "is_late": report.submission_date > report.due_date,
            "resubmission_flag": report.resubmission_flag,
            "comments": report.comments,
        })

    return JsonResponse(data, safe=False)