from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Exists, OuterRef
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from .models import User, Department, CommitteeMember, Announcement, Post, Comment, Like
from .forms import RegistrationForm, LoginForm, ProfileUpdateForm, PostForm, CommentForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Message
from .forms import MessageForm

def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)

def active_member_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        if request.user.status != 'active':
            messages.warning(request, 'Your account is pending approval.')
            return redirect('core:homepage')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def homepage(request):
    announcements = Announcement.objects.all()[:3]
    total_members = User.objects.filter(status='active').count()
    committees = CommitteeMember.objects.filter(is_current=True)[:4]
    context = {
        'announcements': announcements,
        'total_members': total_members,
        'committees': committees,
    }
    return render(request, 'core/homepage.html', context)

def about(request):
    return render(request, 'core/about.html')

def committee_page(request):
    current_committee = CommitteeMember.objects.filter(is_current=True).order_by('order')
    past_committees = CommitteeMember.objects.filter(is_current=False).order_by('-session_year')
    return render(request, 'core/committee.html', {
        'current_committee': current_committee,
        'past_committees': past_committees,
    })

@active_member_required
def member_directory(request):
    members = User.objects.filter(status='active')
    
    search_query = request.GET.get('search', '')
    department_id = request.GET.get('department', '')
    batch = request.GET.get('batch', '')
    
    if search_query:
        members = members.filter(full_name__icontains=search_query)
    if department_id:
        members = members.filter(department_id=department_id)
    if batch:
        members = members.filter(batch=batch)
    
    paginator = Paginator(members, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    departments = Department.objects.all()
    batches = User.objects.filter(status='active').values_list('batch', flat=True).distinct().order_by('-batch')
    
    return render(request, 'core/member_directory.html', {
        'page_obj': page_obj,
        'departments': departments,
        'batches': batches,
        'search_query': search_query,
        'selected_department': department_id,
        'selected_batch': batch,
    })

@active_member_required
def member_profile(request, user_id):
    member = get_object_or_404(User, id=user_id, status='active')
    return render(request, 'core/member_profile.html', {'member': member})

def register(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.status = 'pending'
            user.save()
            messages.success(request, 'Registration successful! Please wait for admin approval.')
            return redirect('core:login')
    else:
        form = RegistrationForm()
    
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        # ✅ Correct way: pass request as first argument, data as keyword
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.full_name}!')
                return redirect('core:dashboard')
        # If form invalid, it will re-render with errors
    else:
        form = LoginForm()
    
    return render(request, 'core/login.html', {'form': form})



def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('core:homepage')   # add namespace

from django.utils import timezone
from .models import Event, Announcement

@active_member_required
def dashboard(request):
    posts = Post.objects.select_related('user').prefetch_related('comments', 'comments__user').annotate(
        user_has_liked=Exists(Like.objects.filter(post=OuterRef('pk'), user=request.user))
    ).all()
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.save()
            messages.success(request, 'Post created!')
            return redirect('core:dashboard')
    else:
        form = PostForm()

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- Upcoming events (published, date >= now) ---
    upcoming_events = Event.objects.filter(
        status='published',
        date__gte=timezone.now()
    ).order_by('date')[:5]   # limit to 5

    # --- Recent announcements (latest 5) ---
    recent_announcements = Announcement.objects.all().order_by('-is_pinned', '-created_at')[:5]

    context = {
        'form': form,
        'page_obj': page_obj,
        'upcoming_events': upcoming_events,
        'recent_announcements': recent_announcements,
    }
    return render(request, 'core/dashboard.html', context)

@active_member_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
        post.likes_count -= 1
    else:
        post.likes_count += 1
    post.save()
    return JsonResponse({'likes_count': post.likes_count, 'liked': created})

@active_member_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.user = request.user
            comment.save()
            messages.success(request, 'Comment added!')
        else:
            messages.error(request, 'Failed to add comment. Please try again.')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('core:dashboard')))

@active_member_required
def announcements_page(request):
    announcements = Announcement.objects.all()
    paginator = Paginator(announcements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'core/announcements.html', {'page_obj': page_obj})




def events_list(request):
    """Public page showing all published events (upcoming & past)"""
    events = Event.objects.filter(status='published').order_by('-date')
    paginator = Paginator(events, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'core/events.html', {'page_obj': page_obj})


def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id, status='published')
    return render(request, 'core/event_detail.html', {'event': event, 'now': timezone.now()})



@active_member_required
def view_profile(request):
    """Display the logged-in user's profile."""
    return render(request, 'core/view_profile.html', {'profile_user': request.user})

@active_member_required
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


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect('core:dashboard')   # ✅ redirect to dashboard
    return redirect('core:dashboard')

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == 'POST':
        post.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)




@login_required
def inbox(request):
    received_messages = request.user.received_messages.all()
    unread_count = received_messages.filter(is_read=False).count()
    return render(request, 'core/inbox.html', {
        'messages': received_messages,
        'unread_count': unread_count,
    })

@login_required
def view_message(request, message_id):
    message = get_object_or_404(Message, id=message_id, recipient=request.user)
    if not message.is_read:
        message.is_read = True
        message.save()
    return render(request, 'core/message_detail.html', {'message': message})

@login_required
def send_message(request, user_id):
    recipient = get_object_or_404(User, id=user_id, status='active')
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.recipient = recipient
            msg.save()
            messages.success(request, f'Your message to {recipient.full_name} has been sent.')
            return redirect('core:member_profile', user_id=recipient.id)
    else:
        form = MessageForm()
    return render(request, 'core/send_message_modal.html', {
        'form': form,
        'recipient': recipient,
    })



