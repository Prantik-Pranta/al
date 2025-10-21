from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from User.models import UserProfile, Experience, Education, ConnectionRequest, Connection
from .models import Post, Like, Comment
from notifications.utils import notify
from django.urls import reverse
# --- Connections ---



@login_required
def toggle_like_post(request):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("home")

    post_id = request.POST.get("postId")
    post = get_object_or_404(Post, id=post_id)
    user_profile = get_object_or_404(UserProfile, user=request.user)

    like, created = Like.objects.get_or_create(user=user_profile, post=post)
    if not created:
        # Unlike
        like.delete()
        messages.info(request, "You unliked a post.")
    else:
        # Like
        messages.success(request, "You liked a post.")

        # 🔔 Notify the post owner (but not if they liked their own post)
        if post.user.user != request.user:
            from django.urls import reverse
            from notifications.utils import notify  # uses the helper from the notifications app

            notify(
                recipient=post.user.user,
                notif_type='like',
                message=f"{user_profile.full_name} liked your post",
                url=reverse('home')  # or a post detail URL if you have one
            )

    return redirect("home")

@login_required
def add_comment(request):
    if request.method == "POST":
        content = (request.POST.get("content") or "").strip()
        post_id = request.POST.get("post_id")
        parent_id = request.POST.get("parent_id")
        comment_type = request.POST.get("comment_type") or "parent"

        if not content or not post_id:
            messages.error(request, "Missing required fields.")
            return redirect("home")

        post = get_object_or_404(Post, id=post_id)
        user_profile = get_object_or_404(UserProfile, user=request.user)

        if comment_type == "parent":
            Comment.objects.create(user=user_profile, post=post, content=content)
        else:
            parent_comment = get_object_or_404(Comment, id=parent_id)
            Comment.objects.create(user=user_profile, post=post, content=content, parent=parent_comment)

        messages.success(request, "Comment added.")
        if post.user.user != request.user:
            from notifications.utils import notify
            from django.urls import reverse
            notify(
                post.user.user, 'comment',
                f'{request.user.userprofile.full_name} commented on your post',
                url=reverse('home')
            )
        return redirect("home")

    messages.error(request, "Invalid request method.")
    return redirect("home")

@login_required
def delete_comment(request, comment_id):
    """
    Delete a comment made by the logged-in user.
    """
    comment = get_object_or_404(Comment, id=comment_id)

    # Allow only the comment owner or post owner to delete
    if comment.user.user != request.user and comment.post.user.user != request.user:
        messages.error(request, "You don't have permission to delete this comment.")
        return redirect("home")

    if request.method == "POST":
        comment.delete()
        messages.success(request, "Comment deleted successfully!")
        # Redirect to the same post or home
        return redirect("home")

    # Optional: render a confirm page if GET accessed
    return render(request, "confirm_delete.html", {
        "object": comment,
        "type": "Comment",
        "cancel_url": "home"
    })

@login_required
def create_post(request):
    if request.method == "POST":
        content = (request.POST.get("content") or "").strip()
        image = request.FILES.get("image")  # this supports JPG/PNG/GIF
        audience_university = (request.POST.get("audience_university") or "").strip()

        if not content and not image:
            messages.error(request, "Write something or add an image.")
            return redirect("home")

        user_profile = get_object_or_404(UserProfile, user=request.user)
        Post.objects.create(
            user=user_profile,
            content=content,
            image=image,  # GIFs work here too
            audience_university=audience_university,
        )
        messages.success(request, "Post created successfully!")
        return redirect("home")

    return redirect("home")


@login_required
def share_post(request):
    if request.method == "POST":
        original_post_id = request.POST.get("post_id")
        share_content = (request.POST.get("content") or "").strip()
        audience_university = (request.POST.get("audience_university") or "").strip()

        user_profile = get_object_or_404(UserProfile, user=request.user)

        registered_unis = (
            UserProfile.objects.exclude(university__isnull=True)
            .exclude(university__exact="")
            .values_list("university", flat=True)
            .distinct()
        )
        if audience_university not in registered_unis:
            audience_university = (user_profile.university or "").strip()

        original_post = get_object_or_404(Post, id=original_post_id)

        Post.objects.create(
            user=user_profile,
            content=share_content,
            shared_post=original_post,
            audience_university=audience_university,
        )
        messages.success(request, "Post shared successfully.")
        if original_post.user.user != request.user:
            from notifications.utils import notify
            from django.urls import reverse

            target_user = getattr(original_post.user, 'user', original_post.user)
            message = f"{request.user.userprofile.full_name} shared your post"

            notify(
                target_user,
                'share',
                message,
                url=reverse('home')
            )

        return redirect("home")

    messages.error(request, "Invalid request method.")
    return redirect("home")
# Optional: classic edit/delete using redirects (if you want them outside home)
@login_required
def edit_post(request, id):
    post = get_object_or_404(Post, id=id, user=request.user.userprofile)
    if request.method == "POST":
        content = (request.POST.get("content") or "").strip()
        image = request.FILES.get("image")
        if not content:
            messages.error(request, "Post content is required.")
            return redirect("home")
        post.content = content
        if image:
            post.image = image
        post.save()
        messages.success(request, "Post updated.")
        return redirect("home")
    # If you don't want a separate page, remove this GET branch and do edit inline on home.
    return render(request, "post_edit.html", {"post": post})


@login_required
def delete_post(request, id):
    post = get_object_or_404(Post, id=id, user=request.user.userprofile)
    if request.method == "POST":
        post.delete()
        messages.success(request, "Post deleted.")
        return redirect("home")
    return render(request, "post_delete_confirm.html", {"post": post})

@login_required
def search_results(request):
    """
    Search people by:
      - name (default): full_name contains query
      - university: university contains query  ← NEW
    Accepts GET or POST. Prefers GET to allow shareable URLs.
    """
    # read inputs (GET first so pagination/bookmarks work nicely)
    search_input = request.GET.get("search_input") or request.POST.get("search_input") or ""
    search_by    = (request.GET.get("search_by") or request.POST.get("search_by") or "name").lower()

    # no query → empty state
    if not search_input.strip():
        return render(request, "search_results.html", {
            "search_results": [],
            "query": "",
            "search_by": search_by,
            "request_receivers": [],
            "request_senders": [],
            "connections": [],
        })

    # base queryset: exclude admin/staff
    qs = UserProfile.objects.exclude(user__is_staff=True).exclude(user__is_superuser=True)

    # NEW: filter by university when requested
    if search_by == "university":
        results = qs.filter(university__icontains=search_input.strip())
    else:
        # default: search by name (you can extend to headline/email as needed)
        results = qs.filter(full_name__icontains=search_input.strip())

    # Build connection context so template can render proper buttons/states
    received_requests = ConnectionRequest.objects.filter(receiver=request.user)
    senders   = [req.sender for req in received_requests]        # users who sent me requests
    sent_requests = ConnectionRequest.objects.filter(sender=request.user)
    receivers = [req.receiver for req in sent_requests]          # users I sent requests to

    connection_objs = Connection.objects.filter(Q(user1=request.user) | Q(user2=request.user))
    connections = []
    for c in connection_objs:
        connections.append(c.user2 if c.user1 == request.user else c.user1)

    context = {
        "search_results": results,
        "query": search_input,
        "search_by": search_by,
        "request_receivers": receivers,
        "request_senders": senders,
        "connections": connections,
    }
    return render(request, "search_results.html", context)


@login_required
def send_connection_request(request, user_id):
    """Send a new connection request."""
    sender = request.user
    receiver_profile = get_object_or_404(UserProfile, id=user_id)
    receiver = receiver_profile.user

    if sender == receiver:
        messages.error(request, "You cannot send a connection request to yourself.")
        return redirect('my_connections')

    existing = ConnectionRequest.objects.filter(
        Q(sender=sender, receiver=receiver) | Q(sender=receiver, receiver=sender)
    )
    if existing.exists():
        messages.info(request, "A connection request already exists.")
        return redirect('my_connections')

    ConnectionRequest.objects.create(sender=sender, receiver=receiver)
    messages.success(request, f"Connection request sent to {receiver_profile.full_name}.")

    # 🔔 Notify the receiver
    from django.urls import reverse
    from notifications.utils import notify

    # 🔔 Notify the receiver of connection request
    target_user = getattr(receiver, 'user', receiver)  # ensures it's the actual User instance
    profile_id = getattr(sender.userprofile, 'id', None)
    profile_name = getattr(sender.userprofile, 'full_name', sender.username)

    message = f"{profile_name} sent you a connection request"

    url = reverse('view_profile', args=[profile_id]) if profile_id else reverse('home')

    notify(
        target_user,
        'connection',
        message,
        url=url
    )

    return redirect('my_connections')


@login_required
def accept_connection_request(request, user_id):
    """Accept a connection request and create a Connection."""
    receiver = request.user
    sender = get_object_or_404(UserProfile, id=user_id).user

    try:
        conn_req = ConnectionRequest.objects.get(sender=sender, receiver=receiver)
        Connection.objects.get_or_create(user1=sender, user2=receiver)
        conn_req.delete()
        messages.success(request, "Connection request accepted.")

        # 🔔 Notify sender
        notify(
            sender,
            'connection',
            f'{receiver.userprofile.full_name} accepted your connection request',
            url=reverse('view_profile', args=[receiver.userprofile.id])
        )

    except ConnectionRequest.DoesNotExist:
        messages.error(request, "No such connection request found.")

    return redirect('my_connections')


@login_required
def delete_connection_request(request, user_id):
    """Delete (cancel or ignore) an existing connection request."""
    me = request.user
    other_user = get_object_or_404(UserProfile, id=user_id).user

    deleted_count, _ = ConnectionRequest.objects.filter(
        Q(sender=me, receiver=other_user) | Q(sender=other_user, receiver=me)
    ).delete()

    if deleted_count:
        messages.info(request, "Connection request deleted.")
    else:
        messages.warning(request, "No connection request found.")
    return redirect('my_connections')


@login_required
def my_connections(request):
    """Display all connections, pending requests, and suggestions."""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)

    # All accepted connections
    connections_qs = Connection.objects.filter(Q(user1=user) | Q(user2=user))
    connected_users = []
    for conn in connections_qs:
        other = conn.user2 if conn.user1 == user else conn.user1
        if not (other.is_staff or other.is_superuser):
            connected_users.append(other.userprofile)

    # Pending connection requests (received)
    pending_requests = ConnectionRequest.objects.filter(receiver=user)
    pending_users = [
        req.sender.userprofile for req in pending_requests
        if not (req.sender.is_staff or req.sender.is_superuser)
    ]

    # Suggested users (not connected or pending)
    exclude_ids = [p.id for p in connected_users + pending_users]
    suggested_users = (
        UserProfile.objects.exclude(user=user)
        .exclude(user__is_staff=True)
        .exclude(user__is_superuser=True)
        .exclude(id__in=exclude_ids)[:20]
    )

    context = {
        "user_profile": user_profile,
        "connections": connected_users,
        "pending_requests": pending_users,
        "suggested_users": suggested_users,
    }
    return render(request, "my_networks.html", context)