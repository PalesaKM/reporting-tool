from django.utils import timezone
from .models import SubmissionDeadline, ExtensionRequest

def get_effective_deadline(supervisor):
    """
    Returns the effective deadline datetime for a supervisor.
    Considers both the standard deadline and any approved extension.
    Returns None if no deadline exists.
    """
    try:
        deadline = SubmissionDeadline.objects.filter(supervisor=supervisor).latest('due_datetime')
        effective_deadline = deadline.due_datetime

        # Consider the latest approved extension
        approved_extension = ExtensionRequest.objects.filter(
            supervisor=supervisor,
            status="Approved"
        ).order_by("-created_at").first()

        if approved_extension and approved_extension.requested_until:
            effective_deadline = max(effective_deadline, approved_extension.requested_until)

        return effective_deadline
    except SubmissionDeadline.DoesNotExist:
        return None