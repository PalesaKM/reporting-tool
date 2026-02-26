from django import forms
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import (
    WeeklyReport,
    ReportContent,
    Comment,
    DailyReport,
    DailyReportContent,
    DailyReportComment,
    DailyReportSupervisorComment,
    ExtensionRequest,
)

class WeeklyReportForm(forms.ModelForm):
    class Meta:
        model = WeeklyReport
        fields = ["week_number"]
        
        widgets = {
             "week_number": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Week Number", "readonly": "readonly"}),
             
        }
        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_week = timezone.localtime(timezone.now()).isocalendar().week
        if self.instance and self.instance.pk and self.instance.week_number:
            self.fields["week_number"].initial = self.instance.week_number
        else:
            self.fields["week_number"].initial = current_week
        self.fields["week_number"].disabled = True

    def clean_week_number(self):
        if self.instance and self.instance.pk and self.instance.week_number:
            return self.instance.week_number
        return timezone.localtime(timezone.now()).isocalendar().week
    
class ReportContentForm(forms.ModelForm):
    class Meta:
        model= ReportContent
        fields= ["project_name","category", "entry"]
        widgets = {
            "project_name": forms.TextInput(attrs={
                "class": "form-control", 
                "placeholder": "Project Name"
            }),
            "category": forms.Select(attrs= {"class": "form-control"}),
            "entry": forms.Textarea(attrs= {"class": "form-control tinymce-editor", "rows":5, "placeholder": "Enter details for this category..."}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def clean(self):
        cleaned_data= super().clean()
        category = cleaned_data.get('category')
        entry = cleaned_data.get('entry')
        if category and not entry:
            raise forms.ValidationError("An entry is required for each category selected.")
        if not category and entry:
            raise forms.ValidationError("Please select a category for the provided entry.")
        return cleaned_data

class CommentForm(forms.ModelForm):
    class Meta:
        model= Comment
        fields= ["comment_text"]
        widgets = {
            "comment_text": forms.Textarea(attrs={
                "class": "form-control", 
                "rows": 5, 
                "placeholder": "Enter review comments here..."
            }),
        }
    def clean_comment_text(self):
        comment_text = self.cleaned_data["comment_text"]
        if not comment_text.strip():
            raise forms.ValidationError("Comment cannot be empty.")
        return comment_text

class DailyReportCommentForm(forms.ModelForm):
    class Meta:
        model = DailyReportComment
        fields = ["comment_text"]
        widgets = {
            "comment_text": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Enter review comments here..."
            }),
        }

    def clean_comment_text(self):
        comment_text = self.cleaned_data["comment_text"]
        if not comment_text.strip():
            raise forms.ValidationError("Comment cannot be empty.")
        return comment_text

class DailyReportSupervisorCommentForm(forms.ModelForm):
    class Meta:
        model = DailyReportSupervisorComment
        fields = ["comment_text"]
        widgets = {
            "comment_text": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Enter review comments here..."
            }),
        }

    def clean_comment_text(self):
        comment_text = self.cleaned_data["comment_text"]
        if not comment_text.strip():
            raise forms.ValidationError("Comment cannot be empty.")
        return comment_text

class ReportStatusForm(forms.ModelForm):
    class Meta:
        model= WeeklyReport
        fields = ["status"]
        widgets={
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices= WeeklyReport.STATUS_CHOICES

ReportContentInlineFormSet = inlineformset_factory(
    WeeklyReport,
    ReportContent,
    form=ReportContentForm,
    fields=["project_name","category", "entry"],
    extra=1,
    can_delete= True,
    validate_min=True, 
)

class DailyReportForm(forms.ModelForm):
    class Meta:
        model = DailyReport
        fields = ["project_name", "supervisor"]
        widgets = {
            "report_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "project_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Project Name"
            }),
            "supervisor": forms.Select(attrs={
                "class": "form-control",
            }),
        }

class DailyReportContentForm(forms.ModelForm):
    class Meta:
        model = DailyReportContent
        fields = ["project_name", "category", "entry"]
        widgets = {
            "project_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Project Name"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "entry": forms.Textarea(attrs={
                "class": "form-control tinymce-editor",
                "rows": 5,
                "placeholder": "Enter details for this category..."
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        entry = cleaned_data.get("entry")
        if category and not entry:
            raise forms.ValidationError("An entry is required for each category selected.")
        if not category and entry:
            raise forms.ValidationError("Please select a category for the provided entry.")
        return cleaned_data

class DailyReportStatusForm(forms.ModelForm):
    class Meta:
        model = DailyReport
        fields = ["status"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = DailyReport.STATUS_CHOICES

class ExtensionRequestForm(forms.ModelForm):
    class Meta:
        model = ExtensionRequest
        fields = ["requested_until", "reason"]
        widgets = {
            "requested_until": forms.DateTimeInput(attrs={
                "class": "form-control",
                "type": "datetime-local"
            }),
            "reason": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Optional: explain why you need an extension..."
            }),
        }

class ExtensionDecisionForm(forms.ModelForm):
    class Meta:
        model = ExtensionRequest
        fields = ["status", "manager_comment"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "manager_comment": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional comment for approval/rejection..."
            }),
        }

# Inline formset for daily reports
DailyReportContentInlineFormSet = inlineformset_factory(
    DailyReport,
    DailyReportContent,
    form=DailyReportContentForm,
    fields=["project_name", "category", "entry"],
    extra=1,
    can_delete=True,
    validate_min=True,
)
