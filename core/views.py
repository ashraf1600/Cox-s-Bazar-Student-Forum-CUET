from functools import wraps
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Exists, OuterRef, Count
from django.http import JsonResponse, HttpResponseRedirect
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from .models import User, Department, CommitteeMember, Announcement, Post, Comment, Like, Event, EventRegistration, PhotoGallery
from .boards import board_list, board_for
from .forms import RegistrationForm, LoginForm, ProfileUpdateForm, PostForm, CommentForm, PhotoGalleryForm, SwitchToAlumniForm


def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


def parse_int(value):
    """Turn a query-string value into an int, or None if it's missing/invalid
    (so ?batch=abc filters nothing instead of crashing with a 500)."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def verified_alumni():
    """Active members an admin has verified as alumni. Self-declared alumni
    are not listed until verified."""
    return User.objects.filter(status='active', is_alumni_verified=True)


def redirect_back(request, fallback):
    """Redirect to the page the user came from, but only if it's on this site."""
    target = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return HttpResponseRedirect(target)
    return redirect(fallback)


# ── Access control ────────────────────────────────────────────────────────
# Public:            home, about, events, notices, gallery, committee, advisory panel,
#                    alumni directory, login/register/password reset.
# Signed in (any):   your own profile, view and edit (pending members can finish it
#                    while they wait for approval), logout.
# Approved members:  forum, threads, posting, member directory and profiles,
#                    messaging, event registration, switching to alumni.
# Admins:            gallery management (Django admin has its own staff check).

def redirect_to_login(request):
    """Send an anonymous visitor to login, coming back to the exact page (query string included)."""
    return redirect(f"{reverse('core:login')}?{urlencode({'next': request.get_full_path()})}")


def end_deactivated_session(request):
    """An admin deactivated this account while it was logged in: sign it out."""
    logout(request)
    messages.error(request, 'Your account has been deactivated. Contact the committee if you think this is a mistake.')
    return redirect('core:login')


def signed_in_required(view_func):
    """Any signed-in account that hasn't been deactivated, including ones awaiting approval."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request)
        if request.user.status == 'inactive':
            return end_deactivated_session(request)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def active_member_required(view_func):
    """Approved members only. Pending accounts go to their profile, where they can finish it."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request)
        if request.user.status == 'inactive':
            return end_deactivated_session(request)
        if request.user.status != 'active':
            messages.info(request, 'That page opens once the committee approves your account. Meanwhile, finish your profile.')
            return redirect('core:view_profile')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request)
        if not is_admin(request.user):
            messages.error(request, 'Only admins can access that page.')
            return redirect('core:homepage')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def community_stats():
    """Real numbers for public pages (no invented "500+" figures)."""
    active = User.objects.filter(status='active')
    return {
        'members': active.count(),
        'alumni': verified_alumni().count(),
        'batches': active.filter(batch__isnull=False).values('batch').distinct().count(),
        'events_held': Event.objects.filter(status='published', date__lt=timezone.now()).count(),
        'topics': Post.objects.count(),
    }


def homepage(request):
    now = timezone.now()
    context = {
        'announcements': Announcement.objects.select_related('admin')[:3],
        'stats': community_stats(),
        'boards': board_list(),
        'upcoming_events': Event.objects.filter(status='published', date__gte=now).order_by('date')[:3],
        'committees': CommitteeMember.objects.filter(is_current=True).select_related('user', 'user__department').order_by('order'),
        'advisors': advisor_cards(),
        'featured_photos': PhotoGallery.objects.order_by('-is_featured', '-uploaded_date')[:5],
    }
    return render(request, 'core/homepage.html', context)

def about(request):
    return render(request, 'core/about.html', {'stats': community_stats()})

def committee_page(request):
    current_committee = CommitteeMember.objects.filter(is_current=True).select_related('user', 'user__department').order_by('order')
    past_committees = CommitteeMember.objects.filter(is_current=False).select_related('user', 'user__department').order_by('-session_year')
    return render(request, 'core/committee.html', {
        'current_committee': current_committee,
        'past_committees': past_committees,
    })

def register(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard' if request.user.status == 'active' else 'core:view_profile')

    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data.get('password')
            user.set_password(password)
            user.status = 'pending'
            user.is_alumni = user.member_type == 'alumni'
            user.is_alumni_verified = False
            user.save()
            messages.success(request, 'Registration successful! Please wait for admin approval.')
            return redirect('core:login')
    else:
        form = RegistrationForm()

    return render(request, 'core/register.html', {'form': form})


@active_member_required
def member_directory(request):
    members = User.objects.filter(status='active').select_related('department')
    search_query = request.GET.get('search', '').strip()
    department_id = parse_int(request.GET.get('department'))
    batch = parse_int(request.GET.get('batch'))

    if search_query:
        members = members.filter(full_name__icontains=search_query)
    if department_id is not None:
        members = members.filter(department_id=department_id)
    if batch is not None:
        members = members.filter(batch=batch)

    members = members.order_by('full_name')
    paginator = Paginator(members, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    departments = Department.objects.all()
    batches = User.objects.filter(status='active', batch__isnull=False).values_list('batch', flat=True).distinct().order_by('-batch')

    return render(request, 'core/member_directory.html', {
        'page_obj': page_obj,
        'departments': departments,
        'batches': batches,
        'search_query': search_query,
        'selected_department': str(department_id or ''),
        'selected_batch': str(batch or ''),
    })

@active_member_required
def member_profile(request, user_id):
    member = get_object_or_404(User, id=user_id, status='active')
    return render(request, 'core/member_profile.html', {'member': member})

def alumni_directory(request):
    """Public alumni directory – shows only admin-verified alumni."""
    alumni_list = verified_alumni().select_related('department')

    search_query = request.GET.get('search', '').strip()
    department_id = parse_int(request.GET.get('department'))
    batch = parse_int(request.GET.get('batch'))
    grad_year = parse_int(request.GET.get('graduation_year'))

    if search_query:
        alumni_list = alumni_list.filter(
            Q(full_name__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(designation__icontains=search_query)
        )
    if department_id is not None:
        alumni_list = alumni_list.filter(department_id=department_id)
    if batch is not None:
        alumni_list = alumni_list.filter(batch=batch)
    if grad_year is not None:
        alumni_list = alumni_list.filter(graduation_year=grad_year)

    alumni_list = alumni_list.order_by('-graduation_year', '-batch', 'full_name')

    paginator = Paginator(alumni_list, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    departments = Department.objects.all()
    base_alumni = verified_alumni()
    batches = base_alumni.filter(batch__isnull=False).values_list('batch', flat=True).distinct().order_by('-batch')
    grad_years = base_alumni.filter(graduation_year__isnull=False).values_list('graduation_year', flat=True).distinct().order_by('-graduation_year')

    return render(request, 'core/alumni_directory.html', {
        'page_obj': page_obj,
        'departments': departments,
        'batches': batches,
        'grad_years': grad_years,
        'search_query': search_query,
        'selected_department': str(department_id or ''),
        'selected_batch': str(batch or ''),
        'selected_grad_year': str(grad_year or ''),
    })

def committee_directory(request):
    committee_members = CommitteeMember.objects.filter(is_current=True).select_related('user', 'user__department')

    search_query = request.GET.get('search', '').strip()
    designation = request.GET.get('designation', '').strip()
    session_year = request.GET.get('session_year', '').strip()

    if search_query:
        committee_members = committee_members.filter(
            Q(user__full_name__icontains=search_query) |
            Q(designation__icontains=search_query)
        )
    if designation:
        committee_members = committee_members.filter(designation__icontains=designation)
    if session_year:
        committee_members = committee_members.filter(session_year=session_year)

    committee_members = committee_members.order_by('order', 'designation')

    designations = CommitteeMember.objects.filter(is_current=True).values_list('designation', flat=True).distinct()
    session_years = CommitteeMember.objects.values_list('session_year', flat=True).distinct().order_by('-session_year')

    return render(request, 'core/committee_directory.html', {
        'committee_members': committee_members,
        'designations': designations,
        'session_years': session_years,
        'search_query': search_query,
        'selected_designation': designation,
        'selected_session_year': session_year,
    })


@ensure_csrf_cookie
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard' if request.user.status == 'active' else 'core:view_profile')

    next_url = request.POST.get('next') or request.GET.get('next', '')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            # AuthenticationForm has already authenticated the user.
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.full_name}!')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return HttpResponseRedirect(next_url)
            return redirect('core:dashboard' if user.status == 'active' else 'core:view_profile')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form, 'next': next_url})


@require_POST
def logout_view(request):
    """POST only, so another site can't log members out with a hidden link or image."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('core:homepage')


# Fields that make a profile useful to other members (used for the completeness meter).
PROFILE_COMPLETENESS_FIELDS = [
    'profile_photo', 'phone', 'department', 'batch', 'blood_group', 'upazila',
    'dob', 'address', 'designation', 'company', 'linkedin',
]


def profile_completeness(user):
    filled = sum(1 for field in PROFILE_COMPLETENESS_FIELDS if getattr(user, field))
    return round(100 * filled / len(PROFILE_COMPLETENESS_FIELDS))


@active_member_required
def dashboard(request):
    me = request.user
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = me
            post.save()
            messages.success(request, 'Your post is live.')
            return redirect('core:dashboard')
        messages.error(request, 'Your post could not be published. Please check the form.')
    else:
        form = PostForm()

    # Feed, optionally filtered by category (?category=Job Opportunity)
    categories = [value for value, _ in Post.CATEGORY_CHOICES]
    active_category = request.GET.get('category', '')
    if active_category not in categories:
        active_category = ''
    posts = Post.objects.select_related('user', 'user__department').prefetch_related('comments', 'comments__user').annotate(
        user_has_liked=Exists(Like.objects.filter(post=OuterRef('pk'), user=me)),
        reply_count=Count('comments', distinct=True),
    )
    if active_category:
        posts = posts.filter(category=active_category)
    sort = request.GET.get('sort', 'latest')
    if sort == 'top':
        posts = posts.order_by('-likes_count', '-reply_count', '-created_at')
    elif sort == 'unanswered':
        posts = posts.filter(reply_count=0).order_by('-created_at')
    else:
        sort = 'latest'
        posts = posts.order_by('-created_at')
    page_obj = Paginator(posts, 10).get_page(request.GET.get('page'))
    boards = board_list()

    now = timezone.now()
    hour = timezone.localtime(now).hour
    greeting = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'

    context = {
        'form': form,
        'page_obj': page_obj,
        'categories': categories,
        'active_category': active_category,
        'active_board': board_for(active_category) if active_category else None,
        'boards': boards,
        'total_topics': sum(b['topics'] for b in boards),
        'sort': sort,
        'greeting': greeting,
        'first_name': me.full_name.split()[0] if me.full_name else '',
        'completeness': profile_completeness(me),
        'stats': {
            'members': User.objects.filter(status='active').count(),
            'alumni': verified_alumni().count(),
            'upcoming': Event.objects.filter(status='published', date__gte=now).count(),
            'my_posts': Post.objects.filter(user=me).count(),
        },
        'upcoming_events': Event.objects.filter(status='published', date__gte=now).order_by('date')[:4],
        'recent_announcements': Announcement.objects.select_related('admin')[:3],
        'new_members': User.objects.filter(status='active').exclude(id=me.id)
                           .select_related('department').order_by('-date_joined')[:5],
        'is_admin': is_admin(me),
    }
    return render(request, 'core/dashboard.html', context)


@require_POST
@active_member_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
    # Recount instead of +1/-1 so simultaneous clicks can't drift the counter.
    likes_count = post.likes.count()
    Post.objects.filter(pk=post.pk).update(likes_count=likes_count)
    return JsonResponse({'likes_count': likes_count, 'liked': created})

@active_member_required
def post_detail(request, post_id):
    """One topic with all of its replies."""
    me = request.user
    post = get_object_or_404(
        Post.objects.select_related('user', 'user__department').annotate(
            user_has_liked=Exists(Like.objects.filter(post=OuterRef('pk'), user=me)),
        ),
        id=post_id,
    )
    replies = post.comments.select_related('user', 'user__department')
    participants = {post.user_id: post.user}
    for reply in replies:
        participants.setdefault(reply.user_id, reply.user)
    related = (Post.objects.filter(category=post.category).exclude(id=post.id)
               .select_related('user').annotate(reply_count=Count('comments'))[:5])
    return render(request, 'core/thread.html', {
        'post': post,
        'board': board_for(post.category),
        'replies': replies,
        'participants': list(participants.values()),
        'related': related,
        'categories': [value for value, _ in Post.CATEGORY_CHOICES],
        'is_admin': is_admin(me),
    })


@require_POST
@active_member_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.user = request.user
        comment.save()
        messages.success(request, 'Reply posted.')
        if request.POST.get('next', '').endswith(f'/post/{post.id}/'):
            return HttpResponseRedirect(f"{reverse('core:post_detail', args=[post.id])}#reply-{comment.id}")
    else:
        messages.error(request, 'Write something before posting a reply.')
    return redirect_back(request, 'core:dashboard')

def announcements_page(request):
    """Public: the same notices already appear on the homepage."""
    announcements = Announcement.objects.select_related('admin')
    paginator = Paginator(announcements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'core/announcements.html', {'page_obj': page_obj})


def events_list(request):
    """Public page: upcoming events first (soonest first), then past events, paginated."""
    now = timezone.now()
    published = Event.objects.filter(status='published')
    upcoming = published.filter(date__gte=now).order_by('date')
    past = published.filter(date__lt=now).order_by('-date')
    page_obj = Paginator(past, 12).get_page(request.GET.get('page'))
    return render(request, 'core/events.html', {
        'upcoming': upcoming,
        'page_obj': page_obj,
        'total': published.count(),
    })


def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id, status='published')
    is_registered = (
        request.user.is_authenticated
        and EventRegistration.objects.filter(event=event, user=request.user).exists()
    )
    return render(request, 'core/event_detail.html', {
        'event': event,
        'now': timezone.now(),
        'registered_count': event.registrations.count(),
        'seats_left': event.seats_left,
        'is_registered': is_registered,
        'can_rsvp': request.user.is_authenticated and request.user.status == 'active',
    })


@require_POST
@active_member_required
def event_rsvp(request, event_id):
    """Toggle the current member's registration for an event."""
    event = get_object_or_404(Event, id=event_id, status='published')
    existing = EventRegistration.objects.filter(event=event, user=request.user).first()
    if existing:
        existing.delete()
        messages.info(request, f'Your registration for "{event.title}" was cancelled.')
    elif event.date < timezone.now():
        messages.error(request, 'This event has already taken place.')
    elif event.seats_left == 0:
        messages.error(request, 'Sorry, this event is full.')
    else:
        try:
            EventRegistration.objects.create(event=event, user=request.user)
            messages.success(request, f'You are registered for "{event.title}".')
        except IntegrityError:
            pass  # double-submit: already registered
    return redirect('core:event_detail', event_id=event.id)


@signed_in_required
def view_profile(request):
    """Display the logged-in user's profile."""
    return render(request, 'core/view_profile.html', {'profile_user': request.user})

@signed_in_required
def update_profile(request):
    """Allow the user to update their profile information."""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('core:view_profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'core/update_profile.html', {'form': form})


@require_POST
@active_member_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    form = PostForm(request.POST, request.FILES, instance=post)
    if form.is_valid():
        form.save()
        messages.success(request, 'Post updated.')
    else:
        errors = '; '.join(f"{field}: {' '.join(errs)}" for field, errs in form.errors.items())
        messages.error(request, f'Post was not updated. {errors}')
    return redirect_back(request, 'core:dashboard')

@require_POST
@active_member_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    # Authors can delete their own posts; admins can remove any post (moderation).
    if post.user_id != request.user.id and not is_admin(request.user):
        return JsonResponse({'success': False, 'error': 'Not allowed.'}, status=403)
    post.delete()
    return JsonResponse({'success': True})


# Faculty advisors shown on the advisory page. Images live in core/static/images/advisors/;
# advisors without a photo there get a placeholder icon.
ADVISORS = [
    {
        'name': 'Shyamal Acharya',
        'designation': 'Assistant Professor, Dept of CE, CUET',
        'role': 'Chief Advisor',
        'email': 'acharya_shyamal@cuet.ac.bd',
        'phone': '+8801716963388',
        'education': 'PhD in Water Resources Engineering (2026), CUET',
        'image': 'images/advisors/shyamal.png',
    },
    {
        'name': 'Kamrul Hasan Chowdhary',
        'designation': 'Assistant Professor, Dept of Mathematics, CUET',
        'role': 'Advisor',
        'email': 'kamrul@cuet.ac.bd',
        'phone': '',
        'education': '',
        'image': '',
    },
    {
        'name': 'Humayun Kabir',
        'designation': 'Professor, Dept of MIE, CUET',
        'role': 'Advisor',
        'email': 'humayun@cuet.ac.bd',
        'phone': '+8801814330170',
        'education': '',
        'image': '',
    },
    {
        'name': 'Sanjay Das',
        'designation': 'Assistant Professor, Dept of CE, CUET',
        'role': 'Advisor',
        'email': 'sanjay@cuet.ac.bd',
        'phone': '+8801811302245',
        'education': 'M.Sc. Engineering in Civil Engineering',
        'linkedin': 'https://linkedin.com/in/sanjaydas',
        'image': 'images/advisors/sanjoy.png',
    },
    {
        'name': 'Dr. Nursadul Mamun',
        'designation': 'Assistant Professor, Dept of ETE, CUET',
        'role': 'Advisor',
        'email': 'nursad.mamun@cuet.ac.bd',
        'phone': '+8801813977506',
        'education': '',
        'image': '',
    },
    {
        'name': 'Fahim Mahmud',
        'designation': 'Assistant Professor, Dept of EEE, CUET',
        'role': 'Advisor',
        'email': 'fahim@cuet.ac.bd',
        'phone': '',
        'education': '',
        'image': '',
    },
]


def advisor_cards():
    """ADVISORS with a resolved image URL; shared by the homepage teaser and the advisory page.
    Official @cuet.ac.bd emails may be shown publicly; phone numbers are for approved members only."""
    return [{
        **advisor,
        'image_url': static(advisor['image']) if advisor['image'] else '',
        'email_is_official': advisor['email'].lower().endswith('cuet.ac.bd'),
    } for advisor in ADVISORS]


def advisory_panel(request):
    advisors = advisor_cards()
    # Approved members who registered as Advisory Panel are listed too.
    listed_emails = {a['email'].lower() for a in ADVISORS}
    for member in User.objects.filter(status='active', member_type='advisory').select_related('department').order_by('full_name'):
        if member.email.lower() in listed_emails:
            continue
        advisors.append({
            'name': member.full_name,
            'designation': member.designation,
            'role': 'Advisor',
            'email': member.email,
            'phone': '',
            'education': '',
            'linkedin': member.linkedin,
            'image_url': member.profile_photo.url if member.profile_photo else '',
            'email_is_official': member.email.lower().endswith('cuet.ac.bd'),
        })
    is_member = request.user.is_authenticated and request.user.status == 'active'
    return render(request, 'core/advisory_panel.html', {'advisors': advisors, 'is_member': is_member})


def gallery_view(request):
    category = request.GET.get('category', '').strip()
    photos = PhotoGallery.objects.all()
    if category:
        photos = photos.filter(category=category)

    paginator = Paginator(photos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = PhotoGallery.CATEGORY_CHOICES
    return render(request, 'core/gallery.html', {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category,
    })

@admin_required
def admin_gallery_view(request):
    if request.method == 'POST':
        form = PhotoGalleryForm(request.POST, request.FILES)
        images = request.FILES.getlist('image')
        if form.is_valid():
            # The form only validates the first file; check every uploaded file is a real image.
            image_field = forms.ImageField()
            bad_files = []
            for image in images:
                try:
                    image_field.clean(image)
                except forms.ValidationError:
                    bad_files.append(image.name)
            if bad_files:
                messages.error(request, f"These files are not valid images: {', '.join(bad_files)}")
            else:
                for image in images:
                    PhotoGallery.objects.create(
                        title=form.cleaned_data['title'],
                        description=form.cleaned_data['description'],
                        category=form.cleaned_data['category'],
                        is_featured=form.cleaned_data['is_featured'],
                        image=image,
                        uploaded_by=request.user
                    )
                messages.success(request, f'{len(images)} photo(s) uploaded successfully to gallery!')
                return redirect('core:admin_gallery')
    else:
        form = PhotoGalleryForm()

    photos = PhotoGallery.objects.all()
    return render(request, 'core/admin_gallery.html', {
        'form': form,
        'photos': photos,
    })

@require_POST
@admin_required
def delete_gallery_photo(request, photo_id):
    photo = get_object_or_404(PhotoGallery, id=photo_id)
    photo.delete()  # the image file is removed from storage by core.signals
    messages.success(request, 'Photo deleted successfully.')
    return redirect('core:admin_gallery')

@active_member_required
def switch_to_alumni(request):
    if request.user.member_type == 'alumni':
        messages.info(request, 'You are already registered as an alumnus.')
        return redirect('core:view_profile')

    if request.method == 'POST':
        form = SwitchToAlumniForm(request.POST)
        if form.is_valid():
            user = request.user
            user.member_type = 'alumni'
            user.is_alumni = True
            user.is_alumni_verified = False  # an admin must verify before you appear in the alumni directory
            user.graduation_year = form.cleaned_data['graduation_year']
            if form.cleaned_data.get('company'):
                user.company = form.cleaned_data['company']
            if form.cleaned_data.get('designation'):
                user.designation = form.cleaned_data['designation']
            user.save()
            messages.success(request, 'Your status has been updated to Alumni. You will appear in the alumni directory once an admin verifies it.')
            return redirect('core:view_profile')
    else:
        form = SwitchToAlumniForm(initial={
            'company': request.user.company,
            'designation': request.user.designation
        })
    return render(request, 'core/switch_to_alumni.html', {'form': form})
