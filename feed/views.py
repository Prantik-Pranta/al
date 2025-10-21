from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from User.models import UserProfile, Experience, Education, ConnectionRequest, Connection
from .models import Post, Like, Comment
from notifications.utils import notify
from django.urls import reverse

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
        like.delete()
        messages.info(request, "You unliked a post.")
    else:
        messages.success(request, "You liked a post.")

        # 🔔 Notify the post owner (but not if they liked their own post)
        if post.user.user != request.user:
            from django.urls import reverse
            from notifications.utils import notify

            notify(
               recipient=post.user.user,
               notif_type='like',
               message=f"{user_profile.full_name} liked your post",
               url=reverse('home')
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
      - university: university contains query
    """
    # Read inputs
    search_input = request.GET.get("search_input") or request.POST.get("search_input") or ""
    search_by = (request.GET.get("search_by") or request.POST.get("search_by") or "name").lower()

    # Handle POST actions (connection requests)
    if request.method == 'POST':
        action = request.POST.get('action')
        target_id = request.POST.get('target_id')

        if action and target_id:
            target_profile = get_object_or_404(UserProfile, id=target_id)
            handle_connection_action(request, action, target_profile.user)
            # Fix: Use proper URL construction
            from django.urls import reverse
            from urllib.parse import urlencode

            params = urlencode({
                'search_input': search_input,
                'search_by': search_by
            })
            return redirect(reverse('search_results') + '?' + params)

    # No query → empty state
    if not search_input.strip():
        return render(request, "search_results.html", {
            "search_results": [],
            "query": "",
            "search_by": search_by,
        })

    # Base queryset: exclude admin/staff and current user
    qs = UserProfile.objects.exclude(user__is_staff=True).exclude(user__is_superuser=True).exclude(user=request.user)

    # Filter by search criteria
    if search_by == "university":
        results = qs.filter(university__icontains=search_input.strip())
    else:
        results = qs.filter(full_name__icontains=search_input.strip())

    # Add connection status to each profile
    for profile in results:
        profile.connection_status = get_connection_status(request.user, profile.user)

    context = {
        "search_results": results,
        "query": search_input,
        "search_by": search_by,
    }
    return render(request, "search_results.html", context)


def get_connection_status(current_user, target_user):
    """Determine connection status between current user and target user"""
    # Check if already connected
    if Connection.objects.filter(
            Q(user1=current_user, user2=target_user) |
            Q(user1=target_user, user2=current_user)
    ).exists():
        return 'connected'

    # Check if request sent by current user
    if ConnectionRequest.objects.filter(
            sender=current_user, receiver=target_user
    ).exists():
        return 'request_sent'

    # Check if request received from target user
    if ConnectionRequest.objects.filter(
            sender=target_user, receiver=current_user
    ).exists():
        return 'request_received'

    return 'none'


def handle_connection_action(request, action, target_user):
    """Handle connection actions (create, accept, cancel, remove, ignore)"""
    target_profile = UserProfile.objects.get(user=target_user)
    target_name = target_profile.full_name

    if action == 'create':
        # Check if connection request already exists
        existing_request = ConnectionRequest.objects.filter(
            sender=request.user,
            receiver=target_user
        ).first()

        if existing_request:
            messages.info(request, f"Connection request already sent to {target_name}.")
            return

        # Check if they are already connected
        existing_connection = Connection.objects.filter(
            Q(user1=request.user, user2=target_user) |
            Q(user1=target_user, user2=request.user)
        ).first()

        if existing_connection:
            messages.info(request, f"You are already connected with {target_name}.")
            return

        # Check if there's a pending request from the target user
        pending_request = ConnectionRequest.objects.filter(
            sender=target_user,
            receiver=request.user
        ).first()

        if pending_request:
            messages.info(request,
                          f"{target_name} has already sent you a connection request. Please check your pending requests.")
            return

        # Only create if no existing request or connection
        ConnectionRequest.objects.create(sender=request.user, receiver=target_user)
        messages.success(request, f"Connection request sent to {target_name}!")

        # 🔔 Notify the receiver
        from django.urls import reverse
        from notifications.utils import notify

        profile_name = getattr(request.user.userprofile, 'full_name', request.user.username)
        profile_id = getattr(request.user.userprofile, 'id', None)

        message = f"{profile_name} sent you a connection request"
        url = reverse('view_profile', args=[profile_id]) if profile_id else reverse('home')

        notify(
            target_user,
            'connection',
            message,
            url=url
        )

    elif action == 'accept':
        # Accept connection request
        connection_request = ConnectionRequest.objects.filter(
            sender=target_user,
            receiver=request.user
        ).first()

        if not connection_request:
            messages.error(request, f"No connection request found from {target_name}.")
            return

        # Check if already connected
        existing_connection = Connection.objects.filter(
            Q(user1=request.user, user2=target_user) |
            Q(user1=target_user, user2=request.user)
        ).first()

        if existing_connection:
            messages.info(request, f"You are already connected with {target_name}.")
            connection_request.delete()  # Clean up the request
            return

        Connection.objects.create(user1=request.user, user2=target_user)
        connection_request.delete()
        messages.success(request, f"You are now connected with {target_name}!")

        # 🔔 Notify sender
        from django.urls import reverse
        from notifications.utils import notify

        notify(
            target_user,
            'connection',
            f'{request.user.userprofile.full_name} accepted your connection request',
            url=reverse('view_profile', args=[request.user.userprofile.id])
        )

    elif action == 'cancel':
        # Cancel sent request
        connection_request = ConnectionRequest.objects.filter(
            sender=request.user,
            receiver=target_user
        ).first()

        if connection_request:
            connection_request.delete()
            messages.info(request, f"Connection request to {target_name} cancelled.")
        else:
            messages.warning(request, f"No connection request found to {target_name}.")

    elif action == 'remove':
        # Remove existing connection
        connection = Connection.objects.filter(
            Q(user1=request.user, user2=target_user) |
            Q(user1=target_user, user2=request.user)
        ).first()

        if connection:
            connection.delete()
            messages.info(request, f"Connection with {target_name} removed.")
        else:
            messages.warning(request, f"No connection found with {target_name}.")

    elif action == 'ignore':
        # Ignore received request
        connection_request = ConnectionRequest.objects.filter(
            sender=target_user,
            receiver=request.user
        ).first()

        if connection_request:
            connection_request.delete()
            messages.info(request, f"Connection request from {target_name} ignored.")
        else:
            messages.warning(request, f"No connection request found from {target_name}.")

@login_required
def send_connection_request(request, user_id):
    """Send a new connection request."""
    sender = request.user
    receiver_profile = get_object_or_404(UserProfile, id=user_id)
    receiver = receiver_profile.user

    if sender == receiver:
        messages.error(request, "You cannot send a connection request to yourself.")
        return redirect('my_connections')

    # Use the unified handler
    handle_connection_action(request, 'create', receiver)
    return redirect('my_connections')


@login_required
def accept_connection_request(request, user_id):
    """Accept a connection request and create a Connection."""
    receiver = request.user
    sender_profile = get_object_or_404(UserProfile, id=user_id)
    sender = sender_profile.user

    # Use the unified handler
    handle_connection_action(request, 'accept', sender)
    return redirect('my_connections')


@login_required
def delete_connection_request(request, user_id):
    """Delete (cancel or ignore) an existing connection request."""
    me = request.user
    other_profile = get_object_or_404(UserProfile, id=user_id)
    other_user = other_profile.user

    # Determine whether to use 'cancel' or 'ignore'
    if ConnectionRequest.objects.filter(sender=me, receiver=other_user).exists():
        handle_connection_action(request, 'cancel', other_user)
    else:
        handle_connection_action(request, 'ignore', other_user)

    return redirect('my_connections')

@login_required
def remove_connection(request, user_id):
    """Remove an existing connection."""
    me = request.user
    other_profile = get_object_or_404(UserProfile, id=user_id)
    other_user = other_profile.user

    # Use the unified handler
    handle_connection_action(request, 'remove', other_user)
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

    # Add connection status for suggested users
    for profile in suggested_users:
        profile.connection_status = get_connection_status(request.user, profile.user)

    context = {
        "user_profile": user_profile,
        "connections": connected_users,
        "pending_requests": pending_users,
        "suggested_users": suggested_users,
    }
    return render(request, "my_networks.html", context)