from django.shortcuts import render, redirect, get_object_or_404 
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse 
from django.contrib import messages
from django.utils import timezone 
from django.urls import reverse
from django.contrib.auth.views import LoginView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Q, Count, Avg
from datetime import timedelta, datetime, date
import csv
import json
import openpyxl
from .forms import (
    WeeklyReportForm,
    ReportContentInlineFormSet,
    CommentForm,
    ReportStatusForm,
    DailyReportForm,
    DailyReportContentInlineFormSet,
    DailyReportCommentForm,
    DailyReportSupervisorCommentForm,
    DailyReportStatusForm,
    ExtensionRequestForm,
    ExtensionDecisionForm,
)
from .models import (
    Manager,
    WeeklyReport,
    Supervisor,
    Comment,
    SubmissionDeadline,
    Project,
    ReportContent,
    DailyReport,
    ExtensionRequest,
)
from .helpers import get_effective_deadline
from weasyprint import HTML
from django.template.loader import render_to_string
from . import helpers

def download_single_report(request, pk):
    report = get_object_or_404(WeeklyReport, pk=pk)
    
    if not hasattr(request.user, "manager_profile"):
        return HttpResponse("You are not authorized to download this report.", status=403)
    if not request.user.manager_profile.supervisor.filter(pk=report.supervisor.pk).exists():
        return HttpResponse("You are not authorized to download this report.", status=403)

    context = {
        'report': report,
        'supervisor_name': report.supervisor.user.get_full_name() or report.supervisor.user.username,
        'project_name': report.project.name if getattr(report, 'project', None) else 'N/A',
        'date_generated': timezone.now(),
    }

    html_template = render_to_string('reporting_app/single_report_pdf.html', context)

    # Debug test
    # return HttpResponse(html_template)

    pdf_file = HTML(string=html_template, base_url=request.build_absolute_uri()).write_pdf()

    filename = f"Report_{report.pk}_{report.supervisor.user.username}.pdf"
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def calculate_dashboard_metrics(visible_reports):
    """Calculates key metrics and chart data for the manager dashboard."""
    
    total_reports = visible_reports.count()  # <- was team_reports.count()
    
    # 1. Approved/Reviewed Reports count
    approved_reports = visible_reports.filter(
        Q(status='Approved') | Q(status='Reviewed')
    ).count()
    
    # 2. Average Tasks per Report (assuming contents is the task list)
    reports_with_content = visible_reports.annotate(
        task_count=Count('contents')  # assuming related_name='contents'
    )
    avg_tasks_aggregation = reports_with_content.aggregate(avg_tasks=Avg('task_count'))
    avg_tasks = round(avg_tasks_aggregation['avg_tasks'], 1) if avg_tasks_aggregation['avg_tasks'] is not None else 0.0

    # 3. Chart Data (Status Distribution)
    status_counts = visible_reports.values('status').annotate(count=Count('status')).order_by()
    
    labels = []
    counts = []
    
    status_map = dict(WeeklyReport._meta.get_field('status').choices)

    for item in status_counts:
        display_status = status_map.get(item['status'], item['status'])
        labels.append(display_status)
        counts.append(item['count'])
        
    reports_by_status_json = json.dumps({'labels': labels, 'counts': counts})
    
    return {
        'total_reports': total_reports,
        'approved_reports': approved_reports,
        'avg_tasks': avg_tasks,
        'reports_by_status_json': reports_by_status_json,
    }
    
@login_required
def manager_dashboard(request):
    if not hasattr(request.user, "manager_profile"):
        messages.error(request, "You are not authorized to view the Manager Dashboard.")
        return redirect("supervisor_home")

    manager = request.user.manager_profile
    supervised_supervisors = manager.supervisor.all()
    reports = WeeklyReport.objects.filter(
        supervisor__in=supervised_supervisors
    ).select_related("supervisor__user")

    if request.method == "POST":
        action = request.POST.get("action")
        report_pk = request.POST.get("report_pk")
        report = get_object_or_404(reports, pk=report_pk)

        if action == "approve":
            if report.status == "Submitted":
                report.status = "Approved"
                report.save()
                messages.success(request, f"Report #{report.pk} approved.")
            else:
                messages.warning(request, f"Report #{report.pk} is not in Submitted status.")
        elif action == "reject":
            if report.status == "Submitted":
                report.status = "Rejected"
                report.save()
                messages.warning(request, f"Report #{report.pk} rejected.")
            else:
                messages.warning(request, f"Report #{report.pk} is not in Submitted status.")
        elif action == "override":
            if report.status not in ["Approved", "Waived", "Draft"]:
                report.status = "Waived"
                report.save()
                messages.success(request, f"Report #{report.pk} marked as Waived.")
            else:
                messages.warning(request, f"Report #{report.pk} cannot be overridden from {report.status}.")
        else:
            messages.error(request, "Invalid manager action.")

        return redirect("manager_dashboard")

    now = timezone.now()
    reports_data = []
    processed_supervisors = set()

    for report in reports.order_by("-submission_timestamp", "-pk"):
        if report.supervisor_id in processed_supervisors:
            continue

        deadline = SubmissionDeadline.objects.filter(
            supervisor=report.supervisor
        ).order_by("-reporting_week__year", "-reporting_week__week_number").first()
        effective_deadline = None
        if deadline:
            effective_deadline = deadline.extended_datetime or deadline.due_datetime

        submission_time = report.submission_timestamp

        if report.status == "Waived":
            color, status_text = "blue", "WAIVED"
        elif report.status in ["Submitted", "Reviewed", "Approved", "Rejected"] and submission_time:
            if effective_deadline:
                one_hour_before = effective_deadline - timedelta(hours=1)
                if submission_time > effective_deadline:
                    color, status_text = "red", "Missed Deadline"
                elif submission_time > one_hour_before:
                    color, status_text = "orange", "Close to Deadline"
                else:
                    color, status_text = "green", "Well Before"
            else:
                color, status_text = "gray", report.get_status_display()
        else:
            if effective_deadline and effective_deadline < now:
                color, status_text = "red", "Missed Deadline (Not Submitted)"
            else:
                color, status_text = "blue", "Pending Deadline"

        reports_data.append({
            "report": report,
            "supervisor_name": report.supervisor.user.get_full_name() or report.supervisor.user.username,
            "due_datetime": effective_deadline,
            "submission_time": submission_time or "N/A",
            "status_color": color,
            "status_text": status_text,
        })
        processed_supervisors.add(report.supervisor_id)

    for supervisor in supervised_supervisors.exclude(id__in=processed_supervisors).select_related("user"):
        deadline = SubmissionDeadline.objects.filter(
            supervisor=supervisor
        ).order_by("-reporting_week__year", "-reporting_week__week_number").first()
        effective_deadline = None
        if deadline:
            effective_deadline = deadline.extended_datetime or deadline.due_datetime

        if effective_deadline and effective_deadline < now:
            reports_data.append({
                "report": None,
                "supervisor_name": supervisor.user.get_full_name() or supervisor.user.username,
                "due_datetime": effective_deadline,
                "submission_time": "MISSING",
                "status_color": "red",
                "status_text": "CRITICAL: Report Missing",
            })

    metrics = calculate_dashboard_metrics(reports)
    pending_extensions = ExtensionRequest.objects.filter(
        supervisor__in=supervised_supervisors,
        status="Pending",
    ).order_by("-created_at")[:5]

    context = {
        "manager_profile": manager,
        "reports_data": reports_data,
        "reports_awaiting_review": reports.filter(status="Submitted").order_by("-submission_timestamp"),
        "reports_draft_or_rework": reports.filter(Q(status="Draft") | Q(status="Rework")).order_by("-submission_timestamp"),
        "all_reports": reports.order_by("-submission_timestamp"),
        "pending_extension_requests": pending_extensions,
        "approved_waived_draft": ["Approved", "Waived", "Draft"],
        **metrics,
    }

    return render(request, "reporting_app/manager_dashboard.html", context)

@method_decorator(ensure_csrf_cookie, name="dispatch")
class CustomLoginView(LoginView):
    template_name = "registration/login.html"

@login_required
def login_redirect(request):
    if hasattr(request.user, "admin_profile"):
        return redirect("admin_dashboard")
    if hasattr(request.user, "manager_profile"):
        return redirect("manager_dashboard")
    if hasattr(request.user, "supervisor_profile"):
        return redirect("supervisor_home")
    messages.error(request, "Your account does not have a profile assigned.")
    return redirect("login")

@login_required
def report_detail(request, pk):
    
    report_data = get_object_or_404(
        WeeklyReport.objects.select_related("supervisor__department").prefetch_related(
            "contents",
            "comments__manager"
        ),
        pk=pk
    )
    
    
    is_manager = hasattr(request.user, "manager_profile")
    is_supervisor_owner = report_data.supervisor.user == request.user
    
    if is_manager:
        manager_profile = request.user.manager_profile
        manages_supervisor = manager_profile.supervisor.filter(pk=report_data.supervisor.pk).exists()
    else:
        manages_supervisor = False

    can_read = is_supervisor_owner or manages_supervisor
    can_act = manages_supervisor
    is_managing_manager = manages_supervisor

    if not can_read: 
        return HttpResponseForbidden("You do not have permission to view this report.")
    
    
    comment_form = CommentForm()
    status_form = ReportStatusForm()
    
    
    if request.method == "POST" and can_act: # Only managing managers can act
        if 'comment_submit' in request.POST:
            comment_form= CommentForm(request.POST)
            if comment_form.is_valid():
                with transaction.atomic():
                    try:
                        comment= comment_form.save(commit=False)
                        comment.report= report_data
                        comment.manager= request.user.manager_profile
                        comment.save()
                        messages.success(request, "Comment posted successfully.")
                        return redirect('report_detail', pk=pk)
                    except Manager.DoesNotExist:
                        messages.error(request, "Manager profile not found.")
                        return redirect('report_detail', pk=pk)
                    
            else:
                messages.error(request, "Invalid comment form.")
        elif 'approve_submit' in request.POST or 'reject_submit' in request.POST:
            if report_data.status == 'Submitted':
                with transaction.atomic():
                    if 'approve_submit' in request.POST:
                        new_status = 'Approved'
                        status_change_message= 'reviewed and approved'
                        messages.success(request, f'Report #{pk} successfully approved.')
                    else:
                        new_status= 'Rejected'
                        status_change_message= 'reviewed and rejected'
                        messages.warning(request, f'Report #{pk} rejected.')
                    report_data.status = new_status
                    report_data.save()

                    return redirect("report_detail", pk=pk)
            else:
                messages.warning(request, f"Report status is '{report_data.get_status_display()}' and cannot be reviewed.")
                return redirect("report_detail", pk=pk)
            
        elif "status_submit" in request.POST:
            status_form= ReportStatusForm(request.POST)
            if status_form.is_valid():
                with transaction.atomic():
                    report_data.status= status_form.cleaned_data["status"]
                    report_data.save()
                    messages.success(request, f"Report status updated to {report_data.status}.")
                    return redirect("report_detail", pk=pk)
            else:
                messages.error(request, "Invalid status form.")
    edit_window_remaining_seconds = report_data.edit_window_remaining_seconds()
    edit_window_remaining_minutes = (edit_window_remaining_seconds + 59) // 60 if edit_window_remaining_seconds else 0
    context={
        'report': report_data,
        'is_manager': is_manager,
        'is_managing_manager': is_managing_manager, # Added for template logic
        'can_edit': is_supervisor_owner and not report_data.is_locked and report_data.can_edit(),
        'edit_window_remaining_seconds': edit_window_remaining_seconds,
        'edit_window_remaining_minutes': edit_window_remaining_minutes,
        'comment_form': comment_form,
        'status_form': status_form,
    }
    return render(request, "reporting_app/report_detail.html", context)
        
@login_required
def edit_report(request, report_pk): 

    report = get_object_or_404(WeeklyReport.objects.select_related('supervisor'), pk=report_pk)
    current_project = report.project
    if report.supervisor.user != request.user:
        return HttpResponseForbidden("You do not have permission to edit this report.")
    
    if report.is_locked or not report.can_edit():
        return HttpResponseForbidden("Edit window expired. This report can no longer be edited.")
    
    supervisor_profile= report.supervisor
    try:
        today = date.today()
        current_week = today.isocalendar()[1]
        current_year = today.year
        deadline = SubmissionDeadline.objects.filter(
            supervisor=report.supervisor,
            reporting_week__week_number=current_week,
            reporting_week__year=current_year
        ).first()

        due_datetime = deadline.due_datetime if deadline else None
        extended_datetime = deadline.extended_datetime if deadline else None

        if extended_datetime and timezone.now() > extended_datetime:
            return HttpResponseForbidden('The extended deadline for this report has passed.')
        elif due_datetime and timezone.now() > due_datetime:
            return HttpResponseForbidden("The deadline for this report has passed.")
        if deadline.extended_datetime and timezone.now()> deadline.extended_datetime:
            return HttpResponseForbidden('The extended deadline for this report has passed.')
        elif timezone.now()> deadline.due_datetime:
            return HttpResponseForbidden("The deadline for this report has passed.")
    except SubmissionDeadline.DoesNotExist:
        pass
    if request.method == "POST":
        report_form = WeeklyReportForm(request.POST, instance=report)
        formset = ReportContentInlineFormSet(request.POST, instance=report)

        if report_form.is_valid() and formset.is_valid():
            with transaction.atomic():
                
                report = report_form.save(commit=False)
                
                report.status = "Draft" 
                report.save()
                
                formset.save() 
                messages.success(request, f"Report #{report.pk} updated successfully.")
            
            return redirect('report_detail', pk=report.pk) 
        else:
            messages.error(request, "Invalid form data.")
        
    else: 
        report_form = WeeklyReportForm(instance=report)
        formset = ReportContentInlineFormSet(instance=report)
    
    return render(request, "reporting_app/edit_report.html", {
    "report_form": report_form,
    "formset": formset,
    "project": current_project
})

@login_required
def delete_report(request, pk):
    """
    Allows a Supervisor to delete their own report, but only if it is still in Draft status.
    This view is called via the POST method from the edit_report.html form.
    """
    report = get_object_or_404(WeeklyReport, pk=pk)

    # 1. Permission Check: Must be the owner
    if report.supervisor.user != request.user:
        messages.error(request, "You do not have permission to delete this report.")
        return redirect('report_detail', pk=pk)

    # 2. Status Check: Only Drafts can be deleted
    if report.status != 'Draft':
        messages.error(request, f"Report status is '{report.status}'. Only Draft reports can be deleted.")
        return redirect('report_detail', pk=pk)

    if request.method == "POST":
        with transaction.atomic():
            report_pk = report.pk
            report.delete()
            messages.success(request, f"Draft Report #{report_pk} successfully deleted.")
        return redirect('supervisor_home') # Redirect to the supervisor dashboard after deletion

    # If accessed via GET (should not happen with the button setup), redirect them away
    return redirect('supervisor_home')

@login_required
def submit_report(request, report_pk=None):
    try:
        supervisor_profile = request.user.supervisor_profile
    except Supervisor.DoesNotExist:
        return render(request, "reporting_app/error_page.html", {
            "message": "You are not registered as a Supervisor."
        })

    # --------------------------------------------------
    # 1. LOAD OR INITIALIZE REPORT
    # --------------------------------------------------
    if report_pk:
        # Fetch existing report via helper
        report_instance = helpers.get_report_by_pk(report_pk, supervisor_profile)
        if not report_instance:
            return render(request, "reporting_app/error_page.html", {
                "message": "Report not found."
            })
    else:
        # Create a new report instance via helper
        report_instance = helpers.create_weekly_report(supervisor_profile)

    # --------------------------------------------------
    # 2. INITIALIZE MAIN FORM AND INLINE FORMSET
    # --------------------------------------------------
    report_form = WeeklyReportForm(request.POST or None, instance=report_instance)
    content_formset = ReportContentInlineFormSet(request.POST or None, instance=report_instance)

    # --------------------------------------------------
    # 3. HANDLE POST
    # --------------------------------------------------
    if request.method == "POST":
        if report_form.is_valid() and content_formset.is_valid():
            # Save the main report
            report = report_form.save()

            # Save formset entries
            content_formset.instance = report
            content_formset.save()

            # Optionally: redirect to dashboard or report detail page
            return redirect("manager_dashboard")

    # --------------------------------------------------
    # 4. RENDER TEMPLATE
    # --------------------------------------------------
    context = {
        "report_form": report_form,
        "content_formset": content_formset,
        "report_instance": report_instance,
    }
    return render(request, "reporting_app/submit_report.html", context)


@login_required
def report_success(request, report_pk=None):
    context= {'report_pk': report_pk} if report_pk else {}
    return render(request, "reporting_app/report_success.html", context)

@login_required
def list_reports(request):
    """
    Displays a list of all reports submitted by the logged-in Supervisor.
    """
    try:
        # 1. Get the supervisor profile associated with the logged-in user
        supervisor_profile = request.user.supervisor_profile
        
        # 2. Query the reports, filtering by the supervisor profile and ordering by submission time
        reports = WeeklyReport.objects.filter(supervisor=supervisor_profile).order_by('-submission_timestamp')

    except Supervisor.DoesNotExist:
        if hasattr(request.user, "manager_profile"):
            messages.warning(request, "Redirecting to your Manager Dashboard.")
            return redirect('manager_dashboard')
        # Handle cases where the user is not registered as a supervisor
        return render(request, "reporting_app/error_page.html", {"message": "You are not registered as a Supervisor."})

    context = {
        'reports': reports,
        'page_title': "My Submitted Reports"
    }
    return render(request, "reporting_app/list_reports.html", context)

@login_required
def supervisor_home(request):
    """
    Supervisor landing page providing options to submit/resume report or view reports.
    """
    try:
        supervisor_profile = request.user.supervisor_profile
    except Supervisor.DoesNotExist:
        if hasattr(request.user, "manager_profile"):
            return redirect('manager_dashboard')
        return render(request, "reporting_app/error_page.html", {"message": "You are not registered as a Supervisor."})
    
    # Check for an existing DRAFT to provide the "Resume" option
    report_draft = None
    try:
        report_draft = WeeklyReport.objects.get(supervisor=supervisor_profile, status='Draft')
    except WeeklyReport.DoesNotExist:
        pass 
    dashboard_title = "Supervisor Report Submission"   
    latest_extension_request = ExtensionRequest.objects.filter(
        supervisor=supervisor_profile
    ).order_by("-created_at").first()

    context = {
        'report_draft': report_draft,
        'page_title': 'Supervisor Dashboard',
        'dashboard_title': dashboard_title,
        'latest_extension_request': latest_extension_request,
    }
    
    # Check if the user is a manager here to show a manager link
    is_manager = hasattr(request.user, "manager_profile")
    if is_manager:
        context['is_manager'] = True
        context['manager_link'] = "manager_dashboard" # Assuming you'll create this later

    return render(request, "reporting_app/supervisor_home.html", context)

@login_required
def request_extension(request):
    try:
        supervisor_profile = request.user.supervisor_profile
    except Supervisor.DoesNotExist:
        return HttpResponseForbidden("Supervisors only.")

    report_pk = request.GET.get("report_pk")
    report_instance = None
    if report_pk:
        report_instance = get_object_or_404(WeeklyReport, pk=report_pk, supervisor=supervisor_profile)

    if request.method == "POST":
        form = ExtensionRequestForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                extension = form.save(commit=False)
                extension.supervisor = supervisor_profile
                extension.report = report_instance
                extension.status = "Pending"
                extension.save()
            messages.success(request, "Extension request submitted. Your manager will review it.")
            return redirect("supervisor_home")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ExtensionRequestForm()

    recent_requests = ExtensionRequest.objects.filter(
        supervisor=supervisor_profile
    ).select_related("report").order_by("-created_at")[:10]

    return render(request, "reporting_app/request_extension.html", {
        "form": form,
        "report": report_instance,
        "recent_requests": recent_requests,
    })

@login_required
def manager_extension_requests(request):
    if not hasattr(request.user, "manager_profile"):
        return HttpResponseForbidden("Managers only.")

    manager_profile = request.user.manager_profile
    managed_supervisors = manager_profile.supervisor.all()

    if request.method == "POST":
        request_id = request.POST.get("request_id")
        extension_request = get_object_or_404(
            ExtensionRequest,
            pk=request_id,
            supervisor__in=managed_supervisors,
        )
        form = ExtensionDecisionForm(request.POST, instance=extension_request)
        if form.is_valid():
            with transaction.atomic():
                decision = form.save(commit=False)
                decision.save()
                if decision.status == "Approved":
                    deadline, _ = SubmissionDeadline.objects.get_or_create(supervisor=decision.supervisor)
                    if deadline.extended_datetime is None or decision.requested_until > deadline.extended_datetime:
                        deadline.extended_datetime = decision.requested_until
                        deadline.save()
            messages.success(request, f"Extension request #{extension_request.pk} updated.")
            return redirect("manager_extension_requests")
        messages.error(request, "Invalid decision form.")

    pending_requests = ExtensionRequest.objects.filter(
        supervisor__in=managed_supervisors,
        status="Pending",
    ).select_related("supervisor", "report").order_by("-created_at")

    recent_requests = ExtensionRequest.objects.filter(
        supervisor__in=managed_supervisors,
    ).select_related("supervisor", "report").order_by("-created_at")[:20]

    return render(request, "reporting_app/manager_extension_requests.html", {
        "pending_requests": pending_requests,
        "recent_requests": recent_requests,
    })

@login_required
def submit_daily_report(request, report_pk=None):
    if not hasattr(request.user, "admin_profile"):
        return HttpResponseForbidden("Admins only.")

    admin_profile = request.user.admin_profile
    supervisor_queryset = Supervisor.objects.filter(department=admin_profile.department)
    report_instance = None
    if report_pk:
        report_instance = get_object_or_404(DailyReport, pk=report_pk, admin=admin_profile)
        if not report_instance.can_edit():
            messages.error(request, "This daily report can no longer be edited.")
            return redirect("admin_daily_reports")

    if request.method == "POST":
        form = DailyReportForm(request.POST, instance=report_instance)
        form.fields["supervisor"].queryset = supervisor_queryset
        formset = DailyReportContentInlineFormSet(request.POST, instance=report_instance)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                report = form.save(commit=False)
                report.admin = admin_profile
                if not report.status:
                    report.status = "Submitted"
                report.save()

                formset.instance = report
                formset.save()

            messages.success(request, "Daily report submitted.")
            return redirect("admin_dashboard")

    else:
        form = DailyReportForm(instance=report_instance)
        form.fields["supervisor"].queryset = supervisor_queryset
        formset = DailyReportContentInlineFormSet(instance=report_instance)

    edit_window_remaining_seconds = report_instance.edit_window_remaining_seconds() if report_instance else 0
    edit_window_remaining_minutes = (edit_window_remaining_seconds + 59) // 60 if edit_window_remaining_seconds else 0
    return render(request, "reporting_app/admin_submit_daily.html", {
        "form": form,
        "formset": formset,
        "report_type": "daily",
        "is_editing": report_instance is not None,
        "edit_window_remaining_seconds": edit_window_remaining_seconds,
        "edit_window_remaining_minutes": edit_window_remaining_minutes,
    })

@login_required
def admin_dashboard(request):
    if not hasattr(request.user, "admin_profile"):
        return HttpResponseForbidden("Admins only.")

    admin_profile = request.user.admin_profile
    recent_reports = (
        DailyReport.objects.filter(admin=admin_profile)
        .select_related("supervisor", "project")
        .order_by("-submission_timestamp", "-pk")[:10]
    )

    return render(request, "reporting_app/admin_dashboard.html", {
        "recent_reports": recent_reports,
        "page_title": "Admin Dashboard",
    })

@login_required
def admin_daily_reports(request):
    if not hasattr(request.user, "admin_profile"):
        return HttpResponseForbidden("Admins only.")

    admin_profile = request.user.admin_profile
    reports = (
        DailyReport.objects.filter(admin=admin_profile)
        .select_related("supervisor", "project")
        .order_by("-submission_timestamp", "-pk")
    )

    return render(request, "reporting_app/admin_daily_reports.html", {
        "reports": reports,
        "page_title": "My Daily Reports",
    })

@login_required
def supervisor_daily_reports(request):
    try:
        supervisor = request.user.supervisor_profile
    except Supervisor.DoesNotExist:
        return HttpResponseForbidden("Supervisors only.")

    reports = DailyReport.objects.filter(
        supervisor=supervisor
    ).select_related("admin", "project").order_by("-submission_timestamp", "-pk")

    return render(request, "reporting_app/supervisor_daily_reports.html", {
        "reports": reports
    })

@login_required
def supervisor_daily_report_detail(request, pk):
    try:
        supervisor = request.user.supervisor_profile
    except Supervisor.DoesNotExist:
        return HttpResponseForbidden("Supervisors only.")

    report = get_object_or_404(
        DailyReport.objects.select_related("admin", "supervisor", "project").prefetch_related(
            "contents",
            "supervisor_comments__supervisor",
        ),
        pk=pk,
        supervisor=supervisor,
    )

    comment_form = DailyReportSupervisorCommentForm()
    status_form = DailyReportStatusForm(instance=report)

    if request.method == "POST":
        if "comment_submit" in request.POST:
            comment_form = DailyReportSupervisorCommentForm(request.POST)
            if comment_form.is_valid():
                with transaction.atomic():
                    comment = comment_form.save(commit=False)
                    comment.report = report
                    comment.supervisor = supervisor
                    comment.save()
                messages.success(request, "Comment posted successfully.")
                return redirect("supervisor_daily_report_detail", pk=pk)
            messages.error(request, "Invalid comment form.")
        elif "status_submit" in request.POST:
            status_form = DailyReportStatusForm(request.POST, instance=report)
            if status_form.is_valid():
                with transaction.atomic():
                    status_form.save()
                messages.success(request, f"Daily report status updated to {report.status}.")
                return redirect("supervisor_daily_report_detail", pk=pk)
            messages.error(request, "Invalid status form.")

    edit_window_remaining_seconds = report.edit_window_remaining_seconds()
    edit_window_remaining_minutes = (edit_window_remaining_seconds + 59) // 60 if edit_window_remaining_seconds else 0
    return render(request, "reporting_app/supervisor_daily_report_detail.html", {
        "report": report,
        "comment_form": comment_form,
        "status_form": status_form,
        "edit_window_remaining_seconds": edit_window_remaining_seconds,
        "edit_window_remaining_minutes": edit_window_remaining_minutes,
    })

@login_required
def manager_daily_reports(request):
    if not hasattr(request.user, "manager_profile"):
        return HttpResponseForbidden("Managers only.")

    manager_profile = request.user.manager_profile
    managed_supervisors = manager_profile.supervisor.all()
    reports = (
        DailyReport.objects.filter(supervisor__in=managed_supervisors)
        .select_related("admin", "supervisor", "project")
        .order_by("-submission_timestamp", "-pk")
    )

    return render(request, "reporting_app/manager_daily_reports.html", {
        "reports": reports,
        "page_title": "Admin Daily Reports",
    })

@login_required
def daily_report_detail(request, pk):
    if not hasattr(request.user, "manager_profile"):
        return HttpResponseForbidden("Managers only.")

    manager_profile = request.user.manager_profile
    report = get_object_or_404(
        DailyReport.objects.select_related("admin", "supervisor", "project").prefetch_related(
            "contents",
            "comments__manager",
        ),
        pk=pk,
        supervisor__in=manager_profile.supervisor.all(),
    )

    comment_form = DailyReportCommentForm()

    if request.method == "POST" and "comment_submit" in request.POST:
        comment_form = DailyReportCommentForm(request.POST)
        if comment_form.is_valid():
            with transaction.atomic():
                comment = comment_form.save(commit=False)
                comment.report = report
                comment.manager = manager_profile
                comment.save()
            messages.success(request, "Comment posted successfully.")
            return redirect("daily_report_detail", pk=pk)
        messages.error(request, "Invalid comment form.")

    edit_window_remaining_seconds = report.edit_window_remaining_seconds()
    edit_window_remaining_minutes = (edit_window_remaining_seconds + 59) // 60 if edit_window_remaining_seconds else 0
    return render(request, "reporting_app/daily_report_detail.html", {
        "report": report,
        "comment_form": comment_form,
        "edit_window_remaining_seconds": edit_window_remaining_seconds,
        "edit_window_remaining_minutes": edit_window_remaining_minutes,
    })

@login_required
def export_reports_csv(request):
    if not hasattr(request.user, "manager_profile"):
        messages.error(request, "You are not authorized to export reports.")
        return redirect('manager_dashboard')

    manager = request.user.manager_profile
    supervised_supervisors = manager.supervisor.all()
    reports = WeeklyReport.objects.filter(supervisor__in=supervised_supervisors)
    now = timezone.now()

    # Prepare data using helper
    reports_data = []
    processed_supervisors = set()

    for report in reports.order_by('-submission_timestamp', '-pk'):
        if report.supervisor_id in processed_supervisors:
            continue

        effective_deadline = get_effective_deadline(report.supervisor)
        submission_time = report.submission_timestamp

        # Determine status text
        if report.status == 'Waived':
            status_text = 'WAIVED'
        elif report.status in ['Submitted', 'Reviewed', 'Approved', 'Rejected'] and submission_time:
            if effective_deadline:
                one_hour_before = effective_deadline - timedelta(hours=1)
                if submission_time > effective_deadline:
                    status_text = 'Missed Deadline'
                elif submission_time > one_hour_before:
                    status_text = 'Close to Deadline'
                else:
                    status_text = 'Well Before'
            else:
                status_text = report.get_status_display()
        else:
            if effective_deadline and effective_deadline < now:
                status_text = 'Missed Deadline (Not Submitted)'
            else:
                status_text = 'Pending Deadline'

        reports_data.append({
            'supervisor': report.supervisor.user.get_full_name() or report.supervisor.user.username,
            'report_id': report.pk,
            'status': status_text,
            'due_datetime': effective_deadline.strftime("%Y-%m-%d %H:%M") if effective_deadline else 'N/A',
            'submission_time': submission_time.strftime("%Y-%m-%d %H:%M") if submission_time else 'N/A',
            'report_title': getattr(report, 'title', f"Weekly Report {report.pk}")
        })

        processed_supervisors.add(report.supervisor_id)

    # Include supervisors without reports
    for supervisor in supervised_supervisors.exclude(id__in=processed_supervisors):
        effective_deadline = get_effective_deadline(supervisor)
        if effective_deadline and effective_deadline < now:
            reports_data.append({
                'supervisor': supervisor.user.get_full_name() or supervisor.user.username,
                'report_id': 'N/A',
                'status': 'CRITICAL: Report Missing',
                'due_datetime': effective_deadline.strftime("%Y-%m-%d %H:%M"),
                'submission_time': 'MISSING',
                'report_title': 'N/A'
            })

    # Create CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="supervisor_reports_{now.strftime("%Y%m%d_%H%M")}.csv"'

    writer = csv.DictWriter(response, fieldnames=['supervisor', 'report_id', 'report_title', 'due_datetime', 'submission_time', 'status'])
    writer.writeheader()
    for row in reports_data:
        writer.writerow(row)

    return response



