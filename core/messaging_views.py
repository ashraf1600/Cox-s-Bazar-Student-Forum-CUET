"""Chat-style messaging between members.

Any approved (status='active') member can message any other approved member,
unless one of them has blocked the other. Conversations are derived from the
Message table: one conversation per pair of members.
"""
from datetime import timedelta

from django.contrib import messages
from django.db.models import Q, Count, OuterRef, Subquery, IntegerField, Max
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as format_date
from django.views.decorators.http import require_GET, require_POST

from .forms import MessageForm
from .models import User, Message, Block
from .views import active_member_required

THREAD_LIMIT = 200            # newest messages shown when a conversation opens
RATE_LIMIT = 20               # messages a member may send...
RATE_WINDOW = timedelta(minutes=1)  # ...within this window


def _wants_json(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')


def _message_json(msg, me):
    local = timezone.localtime(msg.created_at)
    return {
        'id': msg.id,
        'mine': msg.sender_id == me.id,
        'subject': msg.subject,
        'body': msg.body,
        'is_read': msg.is_read,
        'time': format_date(local, 'g:i A'),
        'date': local.date().isoformat(),
        'date_label': _date_label(local.date()),
    }


def _date_label(day):
    today = timezone.localdate()
    if day == today:
        return 'Today'
    if day == today - timedelta(days=1):
        return 'Yesterday'
    return format_date(day, 'l, F j' if day.year == today.year else 'F j, Y')


def _conversations(me):
    """One row per person `me` has exchanged messages with, newest first."""
    partner_ids = set(
        Message.objects.filter(recipient=me, sender__isnull=False).values_list('sender_id', flat=True)
    ) | set(
        Message.objects.filter(sender=me, recipient__isnull=False).values_list('recipient_id', flat=True)
    )
    latest = Message.objects.filter(
        Q(sender=me, recipient=OuterRef('pk')) | Q(sender=OuterRef('pk'), recipient=me)
    ).order_by('-created_at')
    unread = (
        Message.objects.filter(sender=OuterRef('pk'), recipient=me, is_read=False)
        .values('sender').annotate(n=Count('id')).values('n')
    )
    blocked_ids = set(Block.objects.filter(blocker=me).values_list('blocked_id', flat=True))
    rows = (
        User.objects.filter(id__in=partner_ids)
        .select_related('department')
        .annotate(
            last_at=Subquery(latest.values('created_at')[:1]),
            last_body=Subquery(latest.values('body')[:1]),
            last_subject=Subquery(latest.values('subject')[:1]),
            last_sender_id=Subquery(latest.values('sender_id')[:1]),
            unread=Coalesce(Subquery(unread, output_field=IntegerField()), 0),
        )
        .order_by('-last_at')
    )
    for row in rows:
        row.is_blocked = row.id in blocked_ids
    return list(rows)


def _can_message(me, other):
    """(allowed, reason) for `me` sending a message to `other`."""
    if other.id == me.id:
        return False, "You can't message yourself."
    if other.status != 'active':
        return False, 'This member is not active.'
    if Block.objects.filter(blocker=me, blocked=other).exists():
        return False, 'You blocked this member. Unblock them to send messages.'
    if Block.objects.filter(blocker=other, blocked=me).exists():
        return False, "You can't message this member."
    return True, ''


@active_member_required
def inbox(request):
    return render(request, 'core/messenger.html', {
        'conversations': _conversations(request.user),
        'partner': None,
        'today': timezone.localdate(),
    })


@active_member_required
def conversation(request, user_id):
    me = request.user
    partner = get_object_or_404(User.objects.select_related('department'), id=user_id)
    if partner.id == me.id:
        return redirect('core:inbox')
    # Only approved members can be looked up; others only if you already have a conversation.
    if partner.status != 'active' and not Message.objects.between(me, partner).exists():
        raise Http404('No such member.')

    # Opening the conversation marks everything they sent you as read.
    Message.objects.filter(sender=partner, recipient=me, is_read=False).update(is_read=True)

    thread = list(
        Message.objects.between(me, partner).order_by('-created_at')[:THREAD_LIMIT]
    )[::-1]
    for msg in thread:
        local = timezone.localtime(msg.created_at)
        msg.local_date = local.date()
        msg.date_label = _date_label(msg.local_date)

    can_send, reason = _can_message(me, partner)
    i_blocked = Block.objects.filter(blocker=me, blocked=partner).exists()
    last_mine = next((m for m in reversed(thread) if m.sender_id == me.id), None)

    return render(request, 'core/messenger.html', {
        'conversations': _conversations(me),
        'partner': partner,
        'today': timezone.localdate(),
        'thread': thread,
        'can_send': can_send,
        'cannot_send_reason': reason,
        'i_blocked': i_blocked,
        'last_mine_id': last_mine.id if last_mine else None,
        'last_mine_seen': bool(last_mine and last_mine.is_read),
        'last_id': thread[-1].id if thread else 0,
        'last_date': thread[-1].local_date.isoformat() if thread else '',
        'max_length': Message.MAX_BODY_LENGTH,
    })


@require_POST
@active_member_required
def send_message(request, user_id):
    me = request.user
    partner = get_object_or_404(User, id=user_id)
    allowed, reason = _can_message(me, partner)
    error = None

    if not allowed:
        error = reason
    elif Message.objects.filter(sender=me, created_at__gte=timezone.now() - RATE_WINDOW).count() >= RATE_LIMIT:
        error = "You're sending messages too quickly. Please wait a moment."

    form = MessageForm(request.POST)
    if error is None and not form.is_valid():
        error = 'Message is empty or too long (max %d characters).' % Message.MAX_BODY_LENGTH

    if error:
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': error}, status=429 if 'too quickly' in error else 400)
        messages.error(request, error)
        return redirect('core:conversation', user_id=partner.id)

    msg = form.save(commit=False)
    msg.body = msg.body.strip()
    msg.sender = me
    msg.recipient = partner
    msg.save()

    if _wants_json(request):
        return JsonResponse({'ok': True, 'message': _message_json(msg, me)})
    return redirect('core:conversation', user_id=partner.id)


@require_GET
@active_member_required
def poll(request, user_id):
    """New messages in a conversation since ?after=<id>, plus read receipts."""
    me = request.user
    partner = get_object_or_404(User, id=user_id)
    try:
        after = int(request.GET.get('after', 0))
    except ValueError:
        after = 0

    Message.objects.filter(sender=partner, recipient=me, is_read=False).update(is_read=True)
    new = Message.objects.between(me, partner).filter(id__gt=after).order_by('created_at')[:100]
    seen_upto = Message.objects.filter(sender=me, recipient=partner, is_read=True).aggregate(m=Max('id'))['m'] or 0

    return JsonResponse({
        'messages': [_message_json(m, me) for m in new],
        'seen_upto': seen_upto,
        'unread_total': Message.objects.filter(recipient=me, is_read=False).count(),
    })


@require_GET
@active_member_required
def unread_status(request):
    """Lightweight endpoint the navbar polls to keep the unread badge live."""
    return JsonResponse({'unread': Message.objects.filter(recipient=request.user, is_read=False).count()})


@require_GET
@active_member_required
def search_members(request):
    """Find any approved member to start a conversation with."""
    me = request.user
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    blocked = Block.objects.filter(Q(blocker=me) | Q(blocked=me)).values_list('blocker_id', 'blocked_id')
    hidden = {me.id} | {uid for pair in blocked for uid in pair}
    people = (
        User.objects.filter(status='active')
        .filter(Q(full_name__icontains=q) | Q(serial_no__icontains=q) | Q(company__icontains=q))
        .exclude(id__in=hidden)
        .select_related('department')
        .order_by('full_name')[:8]
    )
    from .templatetags.ui import initials
    return JsonResponse({'results': [{
        'id': p.id,
        'name': p.full_name,
        'sub': ' · '.join(filter(None, [
            p.get_member_type_display(),
            p.department.name if p.department else '',
            f'Batch {p.batch}' if p.batch else '',
        ])),
        'photo': p.profile_photo.url if p.profile_photo else '',
        'initials': initials(p.full_name),
        'hue': sum(map(ord, p.full_name)) % 6,
        'url': reverse('core:conversation', args=[p.id]),
    } for p in people]})


@require_POST
@active_member_required
def toggle_block(request, user_id):
    me = request.user
    other = get_object_or_404(User, id=user_id)
    if other.id == me.id:
        return redirect('core:inbox')
    block = Block.objects.filter(blocker=me, blocked=other).first()
    if block:
        block.delete()
        messages.success(request, f'You unblocked {other.full_name}.')
    else:
        Block.objects.create(blocker=me, blocked=other)
        # Clear their unread messages so they stop counting in your badge.
        Message.objects.filter(sender=other, recipient=me, is_read=False).update(is_read=True)
        messages.info(request, f"You blocked {other.full_name}. They can't message you any more.")
    return redirect('core:conversation', user_id=other.id)


# ── Links from the old email-style inbox keep working ──

@active_member_required
def view_message(request, message_id):
    msg = get_object_or_404(Message, Q(recipient=request.user) | Q(sender=request.user), id=message_id)
    partner_id = msg.sender_id if msg.recipient_id == request.user.id else msg.recipient_id
    if partner_id is None:
        messages.info(request, 'That member is no longer on the platform.')
        return redirect('core:inbox')
    return redirect('core:conversation', user_id=partner_id)


@require_POST
@active_member_required
def reply_message(request, message_id):
    original = get_object_or_404(Message, id=message_id, recipient=request.user)
    if original.sender is None:
        messages.error(request, 'The sender of this message is no longer a member, so you cannot reply.')
        return redirect('core:inbox')
    return send_message(request, original.sender_id)
