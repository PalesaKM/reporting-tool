import os
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

class APIKeyAuthentication(BaseAuthentication):
    """
    Simple API key authentication.
    Send key via header: X-API-KEY
    Or via POST parameter: api_key
    """
    def authenticate(self, request):
        api_key = request.headers.get('X-API-KEY') or request.POST.get('api_key')
        valid_key = os.environ.get("API_KEY")
        if api_key and valid_key and api_key.strip() == valid_key.strip():
            return (None, None)
        if not api_key or api_key != settings.REPORTING_API_KEY:
            raise AuthenticationFailed('Invalid or missing API Key')
        return (None, None)  # No Django user needed