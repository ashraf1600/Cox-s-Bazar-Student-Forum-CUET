from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from .models import User, Department, CommitteeMember, Announcement, Post, Comment, Like
from .forms import RegistrationForm, LoginForm, ProfileUpdateForm, PostForm, CommentForm

def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)

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

@login_required
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

@login_required
def member_profile(request, user_id):
    member = get_object_or_404(User, id=user_id, status='active')
    return render(request, 'core/member_profile.html', {'member': member})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('core:member_profile', user_id=request.user.id)
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'core/edit_profile.html', {'form': form})

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

@login_required
def dashboard(request):
    if request.user.status != 'active':
        messages.warning(request, 'Your account is pending approval.')
        return redirect('core:homepage')

    # --- Timeline posts (unchanged) ---
    posts = Post.objects.select_related('user').all()
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

@login_required
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

@login_required
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
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('core:dashboard')))

@login_required
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
    return render(request, 'core/event_detail.html', {'event': event})