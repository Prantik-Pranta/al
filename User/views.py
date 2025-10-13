from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile, Experience, Education, LicenseCertificate, Skill
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from datetime import date
from django.http import JsonResponse
from feed.models import Post, Like, Comment
from User.models import ConnectionRequest, Connection
from django.db.models import Q  
from .helper_functions import find_connection_posts, find_connection_userprofiles, find_liked_posts, find_child_comments, find_parent_comments, find_connection_count, find_user_posts
from datetime import datetime

# Create your views here.
def login_page(request):
    return render(request, 'login.html')

def landing_page(request):
    return render(request, 'landing_page.html')

def signup_page(request):
    return render(request, 'signup.html')

def create_account(request):
    if request.method == "POST":
        first_name = request.POST.get("firstName")
        last_name = request.POST.get("lastName")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")

        full_name = f"{first_name} {last_name}"

        if User.objects.filter(username=email).exists():
            messages.error(request, "Email is already registered.")
            return redirect("signup") 

        if UserProfile.objects.filter(phone=phone).exists():
            messages.error(request, "Phone number is already registered.")
            return redirect("signup")

        user = User.objects.create_user(
            username=email,
            password=password,
        )

        UserProfile.objects.create(
            user=user,
            full_name=full_name,
            phone=phone
        )

        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")  

    return render(request, "signup.html")

from django.contrib.auth import logout

def signin(request):
    if request.method == "POST":
        # Always log out any existing user before login attempt
        if request.user.is_authenticated:
            logout(request)

        username = request.POST.get('email')
        password = request.POST.get('password')

        # Allow phone number login
        if username.isdigit():
            profile = UserProfile.objects.filter(phone=username).first()
            if profile:
                username = profile.user.username
            else:
                messages.error(request, "Invalid phone number or password.")
                return redirect('login')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

    return render(request, "login.html")


from django.contrib.auth.decorators import login_required
from .models import UserProfile
from feed.models import Post, Comment
from .helper_functions import (
    find_connection_posts, find_connection_count,
    find_liked_posts, find_parent_comments
)

@login_required
def home(request):
    # ✅ Always start by defining user
    user = request.user

    # ✅ Ensure profile exists (no NameError, no crash)
    user_profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'full_name': user.get_full_name() or user.username,
            'phone': '',
        }
    )

    # ✅ Retrieve data for feed
    connection_count = find_connection_count(request.user)
    posts = find_connection_posts(request.user)

    # Build comment maps
    parent_comments_map = {}
    for post in posts:
        parent_comments = find_parent_comments(post)
        parent_comments_map[post.id] = parent_comments

    liked_posts = find_liked_posts(request.user)

    child_comments_map = {}
    for parent_comment_list in parent_comments_map.values():
        for parent_comment in parent_comment_list:
            child_comments = parent_comment.replies.all().order_by('created_at')
            child_comments_map[parent_comment.id] = child_comments

    context = {
        'user_profile': user_profile,
        'posts': posts,
        'liked_posts': liked_posts,
        'parent_comments_map': parent_comments_map,
        'child_comments_map': child_comments_map,
        'connection_count': connection_count,
    }

    return render(request, 'home.html', context)



def add_comment(request):
    if request.POST.get("comment_type") == "parent":
        content = request.POST.get("content")
        post_id = request.POST.get("post_id")
        post = get_object_or_404(Post, id=post_id)
        user_profile = get_object_or_404(UserProfile, user=request.user)
        Comment.objects.create(
            user=user_profile,
            post=post,
            content=content
        )
        return redirect("home")
    else:
        content = request.POST.get("content")
        post_id = request.POST.get("post_id")
        parent_id = request.POST.get("parent_id")
        post = get_object_or_404(Post, id=post_id)
        parent_comment = get_object_or_404(Comment, id=parent_id)
        user_profile = get_object_or_404(UserProfile, user=request.user)
        Comment.objects.create(
            user=user_profile,
            post=post,
            content=content,
            parent=parent_comment
        )
        return redirect("home")
    return redirect("home")





def profile(request):
    user_profile = request.user.userprofile
    experience_list = Experience.objects.filter(userprofile=user_profile)
    education_list = Education.objects.filter(userprofile=user_profile)
    lc_list = LicenseCertificate.objects.filter(userprofile=user_profile)
    skill_list = Skill.objects.filter(userprofile=user_profile)
    skill_edu_map = {}
    skill_exp_map = {}
    skill_lc_map = {}
    for skill in skill_list:
        skill_edu_map[skill.id] = skill.educations.all()
        skill_exp_map[skill.id] = skill.experiences.all()
        skill_lc_map[skill.id] = skill.license_certificates.all()
    context = { 'experience_list': experience_list, 
                'education_list': education_list, 
                'user_profile': user_profile,
                'lc_list': lc_list,
                'skill_list': skill_list,
                'skill_edu_map': skill_edu_map,
                'skill_exp_map': skill_exp_map,
                'skill_lc_map': skill_lc_map
                }
    return render(request, 'profile_page.html', context)

@login_required
def add_experience(request):
    try:
        userprofile = request.user.userprofile  
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect("profile")  

    if request.method == "POST":
        title = request.POST.get("title")
        employment_type = request.POST.get("employmentType")
        company = request.POST.get("company")
        is_current = request.POST.get("currentRole") == "on"
        start_month = request.POST.get("startMonth")
        start_year = request.POST.get("startYearExp")
        end_month = request.POST.get("endMonth")
        end_year = request.POST.get("endYearExp")
        location = request.POST.get("location")
        location_type = request.POST.get("locationType")
        description = request.POST.get("description")
        headline = request.POST.get("headline")  
        # Basic validation
        if not title or not company or not start_month or not start_year:
            messages.error(request, "Please fill all required fields (Title, Company, Start Date).")
            return redirect("add_experience")  # replace with your URL

        # Convert start date
        start_date = date(int(start_year), int(start_month), 1)

        # Convert end date if not current
        if not is_current and end_month and end_year:
            end_date = date(int(end_year), int(end_month), 1)
        else:
            end_date = None

        # Save experience
        Experience.objects.create(
            userprofile=userprofile,
            title=title,
            employment_type=employment_type,
            company=company,
            is_current=is_current,
            start_date=start_date,
            end_date=end_date,
            location=location,
            location_type=location_type,
            description=description
        )

        # Optional: update profile headline
        if headline:
            userprofile.headline = headline
            userprofile.save()

        messages.success(request, "Experience added successfully!")
        return redirect("profile")  # replace with profile URL
    return redirect("profile")  




def add_education(request):
    if request.method == "POST":
        # get the logged-in user's profile
        userprofile = request.user.userprofile  

        # extract form fields
        school = request.POST.get("school")
        degree = request.POST.get("degree")
        field_of_study = request.POST.get("field")
        grade = request.POST.get("grade")
        description = request.POST.get("description")

        # start date (month + year → date object, default to 1st of month)
        start_month = int(request.POST.get("startMonth"))
        start_year = int(request.POST.get("startYearEdu"))
        start_date = date(start_year, start_month, 1)

        # end date (can be empty → None)
        end_month = request.POST.get("endMonth")
        end_year = request.POST.get("endYearEdu")
        end_date = None
        if end_month and end_year:
            end_date = date(int(end_year), int(end_month), 1)

        # create and save Education entry
        Education.objects.create(
            userprofile=userprofile,
            school=school,
            degree=degree,
            field_of_study=field_of_study,
            start_date=start_date,
            end_date=end_date,
            grade=grade,
            description=description
        )

        return redirect("profile") 

def education_detail(request, id):
    edu = Education.objects.get(id=id)
    return JsonResponse({
        "id": edu.id,
        "school": edu.school,
        "degree": edu.degree,
        "field_of_study": edu.field_of_study,
        "grade": edu.grade,
        "description": edu.description,
        "start_date": edu.start_date,
        "end_date": edu.end_date,
    })

def experience_detail(request, id):
    user_profile_obj = request.user.userprofile
    profile_headline = user_profile_obj.headline
    try:
        exp = Experience.objects.get(id=id)
        return JsonResponse({
            "id": exp.id,
            "title": exp.title,
            "employment_type": exp.employment_type,
            "company": exp.company,
            "is_current": exp.is_current,
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "location": exp.location,
            "location_type": exp.location_type,
            "description": exp.description,
            "duration": exp.duration(),
            "profile_headline": profile_headline,
        })
    except Experience.DoesNotExist:
        return JsonResponse({"error": "Experience not found"}, status=404)

def userprofile_detail(request, id):
    try:
        profile = UserProfile.objects.get(id=id)
        return JsonResponse({
            "id": profile.id,
            "full_name": profile.full_name,
            "headline": profile.headline,
            "location": profile.location,
            "summary": profile.summary,
            "phone": profile.phone,

        })
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "UserProfile not found"}, status=404)


def update_profile(request, id):
    userprofile = get_object_or_404(UserProfile, id=id)
    if request.method == "POST":
        userprofile.full_name = request.POST.get("full_name")
        userprofile.headline = request.POST.get("headline")
        userprofile.location = request.POST.get("location")
        userprofile.phone = request.POST.get("phone")
        userprofile.summary = request.POST.get("summary")

        userprofile.save()
        return redirect("profile")

    return JsonResponse({"error": "Invalid request"}, status=400)

def update_profile_photo(request):
    if request.method == "POST" and request.FILES.get("profile_photo"):
        profile = get_object_or_404(UserProfile, user=request.user)
        profile.profile_photo = request.FILES["profile_photo"]
        profile.save()
        return redirect("profile")
    return redirect("profile")

def update_cover_photo(request):
    if request.method == "POST" and request.FILES.get("cover_photo"):
        profile = get_object_or_404(UserProfile, user=request.user)
        profile.background_photo = request.FILES["cover_photo"]
        profile.save()
        return redirect("profile")
    return redirect("profile")

def update_experience(request, id):
    experience_obj = Experience.objects.get(id=id)
    user_profile_obj = request.user.userprofile
    if request.method == "POST":
        experience_obj.title = request.POST.get("title")
        experience_obj.company = request.POST.get("company")
        experience_obj.employment_type = request.POST.get("employment_type")
        experience_obj.is_current = True if request.POST.get("is_current") == "on" else False
        experience_obj.location = request.POST.get("location")
        experience_obj.location_type = request.POST.get("location_type")
        experience_obj.description = request.POST.get("description")
        user_profile_obj.headline = request.POST.get("headline")

        start_month = request.POST.get("start_month")
        start_year = request.POST.get("start_year")
        if start_month and start_year:
            experience_obj.start_date = date(int(start_year), int(start_month), 1)

        if experience_obj.is_current:
            experience_obj.end_date = None
        else:
            end_month = request.POST.get("end_month")
            end_year = request.POST.get("end_year")
            if end_month and end_year:
                experience_obj.end_date = date(int(end_year), int(end_month), 1)
            else:
                experience_obj.end_date = None

        experience_obj.save()
        user_profile_obj.save()
        return redirect("profile")

    return redirect("profile")

@login_required
def update_education(request, id):
    # Get the education object for the logged-in user
    print("edaedaedaedaedaedaaaaaa")
    edu_obj = get_object_or_404(Education, id=id, userprofile=request.user.userprofile)

    if request.method == "POST":
        # Fetch values from form
        edu_obj.school = request.POST.get("school")
        edu_obj.degree = request.POST.get("degree")
        edu_obj.field_of_study = request.POST.get("field")
        edu_obj.grade = request.POST.get("grade")
        edu_obj.description = request.POST.get("description")

        # Start date
        start_month = request.POST.get("start_month")
        start_year = request.POST.get("start_year")
        if start_month and start_year:
            edu_obj.start_date = date(int(start_year), int(start_month), 1)

        # End date
        end_month = request.POST.get("end_month")
        end_year = request.POST.get("end_year")
        print(start_year, end_year)
        is_current = request.POST.get("is_current")  # checkbox value
        if is_current == "on":
            edu_obj.end_date = None
        elif end_month and end_year:
            edu_obj.end_date = date(int(end_year), int(end_month), 1)
        else:
            edu_obj.end_date = None

        # Save updated object
        edu_obj.save()

        # Redirect to profile page (adjust URL pattern as needed)
        return redirect("profile")

def view_profile(request, id):

    my_profile = request.user.userprofile
    user_profile = UserProfile.objects.get(id=id)
    connection = False
    received_request = False
    sent_request = False
    if user_profile != my_profile:
        connection = Connection.objects.filter(
            Q(user1=request.user, user2=user_profile.user) | 
            Q(user1=user_profile.user, user2=request.user)
        ).exists()
        received_request = ConnectionRequest.objects.filter(
            sender=user_profile.user,
            receiver=request.user
        ).exists()
        sent_request = ConnectionRequest.objects.filter(
            sender=request.user,
            receiver=user_profile.user
        ).exists()
    experience_list = Experience.objects.filter(userprofile=user_profile)
    education_list = Education.objects.filter(userprofile=user_profile)
    context = { 
                'experience_list': experience_list, 
                'education_list': education_list, 
                'user_profile': user_profile, 
                'my_profile': my_profile, 
                'connection': connection,
                'received_request': received_request,
                'sent_request': sent_request
                }
    return render(request, 'view_profile.html', context)



def user_activity(request):
    filter_option = request.GET.get('filter', 'posts')
    if filter_option == 'posts':
        user = request.user
        user_profile = UserProfile.objects.get(user=user)
        connection_count = find_connection_count(request.user)
        posts = find_user_posts(request.user)
        parent_comments_map = {}
        for post in posts:
            parent_comments = find_parent_comments(post)
            parent_comments_map[post.id] = parent_comments
        liked_posts = find_liked_posts(request.user)
        child_comments_map = {}
        for parent_comment_list in parent_comments_map.values():
            for parent_comment in parent_comment_list:
                child_comments = parent_comment.replies.all().order_by('created_at')
                child_comments_map[parent_comment.id] = child_comments
        print("child_comments_map:", child_comments_map)
        context =   {
                    'user_profile': user_profile, 
                    'posts': posts, 
                    'liked_posts': liked_posts, 
                    'parent_comments_map': parent_comments_map, 
                    'child_comments_map': child_comments_map,
                    'connection_count': connection_count,
                    'filter_option': filter_option,
                    }
        return render(request, 'my_activity.html', context)
    elif filter_option == 'comments':
        user = request.user
        user_profile = UserProfile.objects.get(user=user)
        liked_posts = find_liked_posts(request.user)
        connection_count = find_connection_count(request.user)
        user_comments = Comment.objects.filter(user=user_profile)
        parent_comments = Comment.objects.filter(id__in=user_comments.values_list("parent_id", flat=True))
        comments = (user_comments | parent_comments).order_by('-created_at')
        commented_posts = []
        commented_posts_set = set()
        for comment in comments:
            if comment.post not in commented_posts_set:
                commented_posts.append(comment.post)
                commented_posts_set.add(comment.post)
        parent_comments_map = {}
        for post in commented_posts:
            for comment in comments:
                if comment.post == post and comment.parent is None:
                    if post.id not in parent_comments_map:
                        parent_comments_map[post.id] = []
                    parent_comments_map[post.id].append(comment)
        
        child_comments_map = {}
        for parent_comment_list in parent_comments_map.values():
            for parent_comment in parent_comment_list:
                child_comments = parent_comment.replies.all().order_by('created_at')
                child_comments_map[parent_comment.id] = child_comments
        context =   {
                    'user_profile': user_profile, 
                    'posts': commented_posts, 
                    'liked_posts': liked_posts, 
                    'parent_comments_map': parent_comments_map, 
                    'child_comments_map': child_comments_map,
                    'connection_count': connection_count,
                    'filter_option': filter_option,
                    }
        return render(request, 'my_activity.html', context)
    else:
        user = request.user
        user_profile = UserProfile.objects.get(user=user)
        connection_count = find_connection_count(request.user)
        # liked_posts= Post.objects.filter(
        #     id__in=Like.objects.filter(user=user_profile).values_list('post_id', flat=True)
        # )
        posts = find_liked_posts(request.user)
        parent_comments_map = {}
        for post in posts:
            parent_comments = find_parent_comments(post)
            parent_comments_map[post.id] = parent_comments
        child_comments_map = {}
        for parent_comment_list in parent_comments_map.values():
            for parent_comment in parent_comment_list:
                child_comments = parent_comment.replies.all().order_by('created_at')
                child_comments_map[parent_comment.id] = child_comments
        print("child_comments_map:", child_comments_map)
        context =   {
                    'user_profile': user_profile, 
                    'posts': posts, 
                    'liked_posts': posts, 
                    'parent_comments_map': parent_comments_map, 
                    'child_comments_map': child_comments_map,
                    'connection_count': connection_count,
                    'filter_option': filter_option,
                    }
        return render(request, 'my_activity.html', context)

def delete_post(request, id):
    post = get_object_or_404(Post, id=id, user=request.user.userprofile)
    post.delete()
    return redirect("user_activity")

def add_license_certificate(request):
    if request.method == "POST":
        userprofile = request.user.userprofile  
        name = request.POST.get("licenseNameLC")
        issuing_organization = request.POST.get("issuingOrgLC")
        issue_date_str = request.POST.get("issueDateLC")
        expiry_date_str = request.POST.get("expiryDateLC")
        certificate_file = request.FILES["certificateFileLC"]
        issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()  
        expiry_date = None
        if expiry_date_str:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()

        LicenseCertificate.objects.create(
            name=name,
            issuing_org=issuing_organization,
            issue_date=issue_date,
            expiry_date=expiry_date,
            certificate_file=certificate_file,
            userprofile=userprofile
        )
        return redirect("profile")  
    return redirect("profile")


@login_required
def get_license_certificate(request, lc_id):
    """
    API endpoint to fetch license/certificate data by ID
    Returns JSON response with license/certificate details
    """
    try:
        # Get the license/certificate object
        lc = get_object_or_404(LicenseCertificate, id=lc_id)
        
        # Check if the user owns this license/certificate
        if lc.userprofile.user != request.user:
            return JsonResponse({
                'error': 'Permission denied'
            }, status=403)
        
        # Prepare response data
        data = {
            'id': lc.id,
            'name': lc.name,
            'issuing_org': lc.issuing_org,
            'issue_date': lc.issue_date.strftime('%Y-%m-%d') if lc.issue_date else None,
            'expiry_date': lc.expiry_date.strftime('%Y-%m-%d') if lc.expiry_date else None,
            'certificate_file': lc.certificate_file.url if lc.certificate_file else None,
        }
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

def edit_license_certificate(request):
    if request.method == "POST":
        lc_id = request.POST.get("lc_id")
        lc = get_object_or_404(LicenseCertificate, id=lc_id, userprofile=request.user.userprofile)
        
        lc.name = request.POST.get("name")
        lc.issuing_org = request.POST.get("issuing_org")
        
        issue_date_str = request.POST.get("issue_date")
        expiry_date_str = request.POST.get("expiry_date")
        
        if issue_date_str:
            lc.issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
        else:
            lc.issue_date = None
        
        if expiry_date_str:
            lc.expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        else:
            lc.expiry_date = None
        
        if "certificate_file" in request.FILES:
            lc.certificate_file = request.FILES["certificate_file"]
        
        lc.save()
        return redirect("profile")
    
    return redirect("profile")



@login_required
def get_skill_context_data(request):
    """
    Fetch experiences, educations, and licenses/certificates for the logged-in user
    to display in the skill form
    """
    try:
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Get all experiences
        experiences = list(user_profile.experiences.all().values(
            'id', 'title', 'company', 'start_date', 'end_date', 'is_current'
        ))
        
        # Get all educations
        educations = list(user_profile.educations.all().values(
            'id', 'school', 'degree', 'field_of_study', 'start_date', 'end_date'
        ))
        
        # Get all licenses & certificates
        licenses = list(user_profile.licenses_certificates.all().values(
            'id', 'name', 'issuing_org', 'issue_date', 'expiry_date'
        ))
        
        return JsonResponse({
            'success': True,
            'data': {
                'experiences': experiences,
                'educations': educations,
                'licenses': licenses
            }
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User profile not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def add_skill(request):
    if request.method == "POST":
        userprofile = request.user.userprofile  
        skill_name = request.POST.get("skillName")
        experience_ids = request.POST.getlist("experiences")
        education_ids = request.POST.getlist("educations")
        license_ids = request.POST.getlist("licenses")

        skill = Skill.objects.create(
            userprofile=userprofile,
            skill_name=skill_name
        )

        for exp_id in experience_ids:
            try:
                exp = Experience.objects.get(id=exp_id, userprofile=userprofile)
                skill.experiences.add(exp)
            except Experience.DoesNotExist:
                continue

        for edu_id in education_ids:
            try:
                edu = Education.objects.get(id=edu_id, userprofile=userprofile)
                skill.educations.add(edu)
            except Education.DoesNotExist:
                continue

        for lic_id in license_ids:
            try:
                lic = LicenseCertificate.objects.get(id=lic_id, userprofile=userprofile)
                skill.license_certificates.add(lic)
            except LicenseCertificate.DoesNotExist:
                continue

        skill.save()
        return redirect("profile")  
    return redirect("profile")


@login_required
def get_skill_details(request, skill_id):
    """
    Fetch details of a specific skill including its associated 
    experiences, educations, and licenses/certificates
    """
    try:
        skill = Skill.objects.get(id=skill_id, userprofile__user=request.user)
        
        # Get skill data
        skill_data = {
            'id': skill.id,
            'skill_name': skill.skill_name,
            'selected_experiences': list(skill.experiences.values_list('id', flat=True)),
            'selected_educations': list(skill.educations.values_list('id', flat=True)),
            'selected_licenses': list(skill.license_certificates.values_list('id', flat=True))
        }
        
        return JsonResponse({
            'success': True,
            'data': skill_data
        })
    except Skill.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Skill not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def edit_skill(request):
    if request.method == "POST":
        userprofile = request.user.userprofile  
        skill_name = request.POST.get("skillName")
        experience_ids = request.POST.getlist("experiences")
        education_ids = request.POST.getlist("educations")
        license_ids = request.POST.getlist("licenses")
        skill_id = request.POST.get("skillId")
        skill = get_object_or_404(Skill, id=skill_id, userprofile=userprofile)
        skill.experiences.clear()
        skill.educations.clear()
        skill.license_certificates.clear()
        skill.skill_name = skill_name
        for exp_id in experience_ids:
            try:
                exp = Experience.objects.get(id=exp_id, userprofile=userprofile)
                skill.experiences.add(exp)
            except Experience.DoesNotExist:
                continue

        for edu_id in education_ids:
            try:
                edu = Education.objects.get(id=edu_id, userprofile=userprofile)
                skill.educations.add(edu)
            except Education.DoesNotExist:
                continue

        for lic_id in license_ids:
            try:
                lic = LicenseCertificate.objects.get(id=lic_id, userprofile=userprofile)
                skill.license_certificates.add(lic)
            except LicenseCertificate.DoesNotExist:
                continue

        skill.save()
        return redirect("profile")  
    return redirect("profile")