from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Message
from django.contrib.auth.models import User

@login_required
def inbox(request):
    # All users the current user has messages with
    users = User.objects.exclude(id=request.user.id)
    return render(request, 'messaging/inbox.html', {'users': users})

@login_required
def chat(request, user_id):
    from_user = request.user
    to_user = User.objects.get(id=user_id)
    messages = Message.objects.filter(
        sender__in=[from_user, to_user],
        receiver__in=[from_user, to_user]
    ).order_by('timestamp')

    if request.method == "POST":
        content = request.POST.get('message')
        if content.strip():
            Message.objects.create(sender=from_user, receiver=to_user, content=content)
        return redirect('chat', user_id=to_user.id)

    return render(request, 'messaging/chat.html', {'to_user': to_user, 'messages': messages})
