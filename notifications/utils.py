from django.urls import reverse
from .models import Notification

def notify(user, type_, message, url=''):
    """
    Create a notification for a user.
    :param user: django.contrib.auth.models.User
    :param type_: 'connection' | 'message' | 'like' | 'comment' | 'share' | 'system'
    :param message: text shown in the list
    :param url: optional URL (string) to redirect when 'Open' is clicked
    """
    if not user:
        return
    Notification.objects.create(
        user=user,
        type=type_,
        message=message,
        url=url or ''
    )
