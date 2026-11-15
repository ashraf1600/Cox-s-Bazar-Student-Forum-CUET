"""The in-site admin panel (/manage/).

Open to site admins: appointed admins, plus the current President, General Secretary and
Assistant General Secretary (see User.is_site_admin). Handing out the admin *role* itself is
reserved for appointed admins (User.is_full_admin).
"""
import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AnnouncementForm, CommitteeMemberForm, EventForm
from .models import Announcement, CommitteeMember, Event, PhotoGallery, STANDARD_DESIGNATIONS, User
from .notify import notify_approved
from .views import admin_required, parse_int, redirect_back


# ── Members ───────────────────────────────────────────────────────────────

@admin_required
def members(request):
    people = User.objects.select_related('department')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if query:
        people = people.filter(Q(full_name__icontains=query) | Q(email__icontains=query)
                               | Q(phone__icontains=query) | Q(serial_no__icontains=query))
    if status in ('active', 'pending', 'inactive'):
        people = people.filter(status=status)
    elif status == 'admins':
        leader_ids = [cm.user_id for cm in CommitteeMember.objects.filter(is_current=True) if cm.grants_admin]
        people = people.filter(Q(role='admin') | Q(is_superuser=True) | Q(id__in=leader_ids, status='active'))
    else:
        status = ''
    page_obj = Paginator(people.order_by('full_name'), 25).get_page(request.GET.get('page'))
    counts = dict(User.objects.values_list('status').annotate(n=Count('id')))
    return render(request, 'core/manage/members.html', {
        'page_obj': page_obj, 'query': query, 'status': status, 'counts': counts,
        'total': sum(counts.values()),
    })


@require_POST
@admin_required
def member_action(request, user_id):
    """Everything an admin can do to one account."""
    me = request.user
    member = get_object_or_404(User, id=user_id)
    action = request.POST.get('action')
    protected = member.is_full_admin and not me.is_full_admin  # leaders can't act on appointed admins

    if protected or (member.is_superuser and not me.is_superuser):
        messages.error(request, f'{member.full_name} is an appointed admin. Only another appointed admin can change that account.')
    elif member.id == me.id and action in ('deactivate', 'decline', 'remove_admin'):
        messages.error(request, 'You cannot do that to your own account.')
    elif action == 'approve' and member.status == 'pending':
        member.status = 'active'
        member.save()  # save() assigns the serial number
        notify_approved(request, member)
        messages.success(request, f'{member.full_name} is approved (member {member.serial_no}).')
    elif action == 'decline' and member.status == 'pending':
        member.status = 'inactive'
        member.save()
        messages.info(request, f"{member.full_name}'s request was declined.")
    elif action == 'deactivate' and member.status == 'active':
        member.status = 'inactive'
        member.save()
        messages.info(request, f'{member.full_name} is deactivated and can no longer log in.')
    elif action == 'reactivate' and member.status == 'inactive':
        member.status = 'active'
        member.save()
        messages.success(request, f'{member.full_name} is active again.')
    elif action == 'verify_alumni' and member.status == 'active':
        member.member_type = 'alumni'
        member.is_alumni = True
        member.is_alumni_verified = True
        member.save()
        messages.success(request, f'{member.full_name} is now a verified alumni.')
    elif action == 'unverify_alumni' and member.is_alumni_verified:
        member.is_alumni_verified = False
        member.save()
        messages.info(request, f'{member.full_name} is no longer listed as a verified alumni.')
    elif action in ('make_admin', 'remove_admin') and me.is_full_admin:
        member.role = 'admin' if action == 'make_admin' else 'member'
        member.save()
        messages.success(request, f"{member.full_name} is {'now an admin' if action == 'make_admin' else 'no longer an admin'}.")
    else:
        messages.error(request, 'That action is not available for this member.')
    return redirect_back(request, 'core:moderation')


# ── Events ────────────────────────────────────────────────────────────────

@admin_required
def events(request):
    now = timezone.now()
    all_events = Event.objects.annotate(going=Count('registrations'))
    return render(request, 'core/manage/events.html', {
        'drafts': all_events.filter(status='draft').order_by('date'),
        'upcoming': all_events.filter(status='published', date__gte=now).order_by('date'),
        'past': all_events.filter(status='published', date__lt=now).order_by('-date')[:30],
    })


@admin_required
def event_edit(request, event_id=None):
    event = get_object_or_404(Event, id=event_id) if event_id else None
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if not event:
            saved.creator = request.user
        if request.POST.get('publish') == '1':
            saved.status = 'published'
        saved.save()
        messages.success(request, f'"{saved.title}" is {"published" if saved.status == "published" else "saved as a draft"}.')
        return redirect('core:manage_events')
    attendees = event.registrations.select_related('user', 'user__department').order_by('created_at') if event else []
    return render(request, 'core/manage/event_form.html', {'form': form, 'event': event, 'attendees': attendees})


@require_POST
@admin_required
def event_delete(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    title = event.title
    event.delete()
    messages.info(request, f'"{title}" was deleted.')
    return redirect('core:manage_events')


@admin_required
def event_attendees_csv(request, event_id):
    """Download the sign-up list for an event (for the registration desk)."""
    event = get_object_or_404(Event, id=event_id)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="event-{event.id}-attendees.csv"'
    response.write('﻿')  # so Excel reads Bangla names correctly
    writer = csv.writer(response)
    writer.writerow(['#', 'Name', 'Member no.', 'Department', 'Batch', 'Phone', 'Email', 'Registered'])
    rows = event.registrations.select_related('user', 'user__department').order_by('created_at')
    for i, r in enumerate(rows, 1):
        u = r.user
        writer.writerow([i, u.full_name, u.serial_no or '', u.department.name if u.department else '', u.batch or '',
                         u.phone or '', u.email, timezone.localtime(r.created_at).strftime('%Y-%m-%d %H:%M')])
    return response


# ── Notices ───────────────────────────────────────────────────────────────

@admin_required
def notices(request):
    page_obj = Paginator(Announcement.objects.select_related('admin'), 20).get_page(request.GET.get('page'))
    return render(request, 'core/manage/notices.html', {'page_obj': page_obj})


@admin_required
def notice_edit(request, notice_id=None):
    notice = get_object_or_404(Announcement, id=notice_id) if notice_id else None
    form = AnnouncementForm(request.POST or None, request.FILES or None, instance=notice)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if not notice:
            saved.admin = request.user
        saved.save()
        messages.success(request, 'Notice posted.' if not notice else 'Notice updated.')
        return redirect('core:manage_notices')
    return render(request, 'core/manage/notice_form.html', {'form': form, 'notice': notice})


@require_POST
@admin_required
def notice_delete(request, notice_id):
    get_object_or_404(Announcement, id=notice_id).delete()
    messages.info(request, 'Notice deleted.')
    return redirect('core:manage_notices')


# ── Committee ─────────────────────────────────────────────────────────────

@admin_required
def committee(request, member_id=None):
    editing = get_object_or_404(CommitteeMember, id=member_id) if member_id else None
    form = CommitteeMemberForm(request.POST or None, instance=editing)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, f'{saved.user.full_name} is {"updated" if editing else "added"} as {saved.designation}.')
        return redirect('core:manage_committee')
    rows = CommitteeMember.objects.select_related('user', 'user__department')
    current = list(rows.filter(is_current=True).order_by('order', 'designation'))
    return render(request, 'core/manage/committee.html', {
        'form': form, 'editing': editing,
        'current': current,
        'current_sessions': sorted({cm.session_year for cm in current}),
        # appointed admins are listed once, in the appointed list
        'leaders': [cm for cm in current if cm.grants_admin and cm.user.status == 'active' and not cm.user.is_full_admin],
        'appointed': User.objects.filter(Q(role='admin') | Q(is_superuser=True), status='active').order_by('full_name'),
        'past': rows.filter(is_current=False).order_by('-session_year', 'order'),
        'designations': STANDARD_DESIGNATIONS,
    })


@require_POST
@admin_required
def committee_action(request, member_id):
    row = get_object_or_404(CommitteeMember.objects.select_related('user'), id=member_id)
    action = request.POST.get('action')
    if action == 'remove':
        row.delete()
        messages.info(request, f'{row.user.full_name} was removed from the {row.session_year} committee.')
    elif action in ('to_past', 'to_current'):
        row.is_current = action == 'to_current'
        row.save(update_fields=['is_current'])
        messages.success(request, f'{row.user.full_name} moved to the {"current" if row.is_current else "past"} committee.')
    return redirect('core:manage_committee')


@require_POST
@admin_required
def committee_archive_session(request):
    """Move a whole session to "past committees" in one go (e.g. after an election)."""
    session = request.POST.get('session_year', '')
    moved = CommitteeMember.objects.filter(is_current=True, session_year=session).update(is_current=False)
    if moved:
        messages.success(request, f'Session {session} ({moved} member{"s" if moved != 1 else ""}) moved to past committees.')
    return redirect('core:manage_committee')


# ── Homepage slideshow ────────────────────────────────────────────────────

@require_POST
@admin_required
def photo_feature(request, photo_id):
    """Featured gallery photos are the slides on the homepage."""
    photo = get_object_or_404(PhotoGallery, id=photo_id)
    photo.is_featured = not photo.is_featured
    photo.save(update_fields=['is_featured'])
    messages.success(request, f'"{photo.title}" {"added to" if photo.is_featured else "removed from"} the homepage slideshow.')
    return redirect('core:admin_gallery')
