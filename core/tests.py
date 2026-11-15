import shutil
import tempfile
from datetime import timedelta

from io import BytesIO

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    User, Department, Post, Comment, Like, Message, Block, Event, EventRegistration, PhotoGallery,
    Notification, Report,
)

TEMP_MEDIA = tempfile.mkdtemp()
STRONG_PASSWORD = 'Sea-Breeze-2026!'


def make_user(email, status='active', **extra):
    extra.setdefault('full_name', email.split('@')[0])
    return User.objects.create_user(email, extra.pop('full_name'), password=STRONG_PASSWORD, status=status, **extra)


@override_settings(MEDIA_ROOT=TEMP_MEDIA, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BaseTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.dept, _ = Department.objects.get_or_create(name='CSE')
        self.member = make_user('u2104001@student.cuet.ac.bd', batch=21, department=self.dept)
        self.other = make_user('u2104002@student.cuet.ac.bd', batch=21, department=self.dept)
        self.admin = make_user('admin@example.com', role='admin', is_staff=True, is_superuser=True)
        self.pending = make_user('u2104003@student.cuet.ac.bd', status='pending')


class ApiSecurityTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_user_cannot_make_themselves_admin(self):
        self.api.force_authenticate(self.member)
        self.api.patch('/api/users/me/', {'role': 'admin', 'status': 'active', 'email': 'x@y.com'}, format='json')
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, 'member')
        self.assertEqual(self.member.email, 'u2104001@student.cuet.ac.bd')

    def test_pending_user_gets_no_token(self):
        response = self.api.post('/api/auth/token/', {'email': self.pending.email, 'password': STRONG_PASSWORD}, format='json')
        self.assertEqual(response.status_code, 401)
        response = self.api.post('/api/auth/token/', {'email': self.member.email, 'password': STRONG_PASSWORD}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_pending_user_cannot_post(self):
        self.api.force_authenticate(self.pending)
        response = self.api.post('/api/posts/', {'content': 'spam'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_only_owner_can_edit_post_admin_can_delete(self):
        post = Post.objects.create(user=self.other, content='mine')
        self.api.force_authenticate(self.member)
        self.assertEqual(self.api.patch(f'/api/posts/{post.id}/', {'content': 'hacked'}, format='json').status_code, 403)
        self.assertEqual(self.api.delete(f'/api/posts/{post.id}/').status_code, 403)
        self.api.force_authenticate(self.admin)
        self.assertEqual(self.api.delete(f'/api/posts/{post.id}/').status_code, 204)

    def test_public_alumni_api_hides_personal_data_and_unverified(self):
        make_user('alum@example.com', member_type='alumni', is_alumni=True, is_alumni_verified=True, phone='0170000000')
        make_user('fake@example.com', member_type='alumni', is_alumni=True, is_alumni_verified=False)
        data = self.api.get('/api/alumni/').json()
        self.assertEqual(len(data), 1)
        for field in ('email', 'phone', 'address', 'dob', 'blood_group'):
            self.assertNotIn(field, data[0])

    def test_invalid_filter_does_not_crash(self):
        self.assertEqual(self.api.get('/api/alumni/?batch=abc&department=x').status_code, 200)

    def test_register_api_enforces_password_rules_and_domain(self):
        response = self.api.post('/api/auth/register/', {
            'full_name': 'X', 'email': 'u2104009@student.cuet.ac.bd.evil.com', 'password': '1', 'confirm_password': '1',
            'member_type': 'running_student', 'batch': 21, 'department': self.dept.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

    def test_self_switch_to_alumni_is_unverified(self):
        self.api.force_authenticate(self.member)
        response = self.api.patch('/api/users/me/', {'member_type': 'alumni', 'graduation_year': 2024}, format='json')
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.member_type, 'alumni')
        self.assertFalse(self.member.is_alumni_verified)


class SerialNumberTests(BaseTestCase):
    def test_non_student_serial_does_not_collide_with_student_ids(self):
        # A student was approved last; the next non-student must not get "student id + 1".
        outsider = make_user('someone@gmail.com', status='pending')
        make_user('u2104096@student.cuet.ac.bd')
        outsider.status = 'active'
        outsider.save()
        self.assertRegex(outsider.serial_no, r'^CSF\d{5}$')
        next_student = make_user('u2104097@student.cuet.ac.bd')
        self.assertEqual(next_student.serial_no, 'CSF2104097')

    def test_student_serial_from_email(self):
        self.assertEqual(self.member.serial_no, 'CSF2104001')


class AuthTests(BaseTestCase):
    def test_login_is_case_insensitive(self):
        response = self.client.post(reverse('core:login'), {'username': 'U2104001@Student.CUET.ac.bd', 'password': STRONG_PASSWORD})
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_login_ignores_offsite_next(self):
        response = self.client.post(reverse('core:login'), {'username': self.member.email, 'password': STRONG_PASSWORD, 'next': 'https://evil.com/'})
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_registration_rejects_weak_password_fake_domain_and_duplicate_case(self):
        data = {
            'full_name': 'New', 'email': 'u2104050@student.cuet.ac.bd.evil.com', 'member_type': 'running_student',
            'batch': 21, 'department': self.dept.id, 'blood_group': 'A+', 'gender': 'Male', 'phone': '1',
            'password': '12345', 'confirm_password': '12345',
        }
        response = self.client.post(reverse('core:register'), data)
        form = response.context['form']
        self.assertIn('email', form.errors)
        self.assertIn('password', form.errors)
        data['email'] = self.member.email.upper()
        response = self.client.post(reverse('core:register'), data)
        self.assertIn('Email is already registered.', response.context['form'].errors['email'])

    def test_registration_rejects_out_of_range_batch(self):
        response = self.client.post(reverse('core:register'), {
            'full_name': 'New', 'email': 'u2104051@student.cuet.ac.bd', 'member_type': 'running_student',
            'batch': 2021, 'department': self.dept.id, 'blood_group': 'A+', 'gender': 'Male', 'phone': '1',
            'password': STRONG_PASSWORD, 'confirm_password': STRONG_PASSWORD,
        })
        self.assertIn('batch', response.context['form'].errors)


class AdminTests(BaseTestCase):
    def test_admin_add_user_hashes_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:core_user_add'), {
            'email': 'new@example.com', 'full_name': 'New Person',
            'password1': STRONG_PASSWORD, 'password2': STRONG_PASSWORD,
            'member_type': 'alumni', 'status': 'active', 'role': 'member',
            'usable_password': 'true',
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['adminform'].form.errors)
        user = User.objects.get(email='new@example.com')
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertNotEqual(user.password, STRONG_PASSWORD)

    def test_approve_action_counts_and_emails(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin:core_user_changelist'), {
            'action': 'approve_members', '_selected_action': [self.pending.id, self.member.id],
        })
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'active')
        self.assertEqual(len(mail.outbox), 1)


class WebViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.member)

    def test_edit_modal_keeps_newlines_and_quotes(self):
        Post.objects.create(user=self.member, content="it's\nline two")
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotContains(response, '\\u0027')
        self.assertNotContains(response, '\\u000A')

    def test_like_requires_post_and_counts_correctly(self):
        post = Post.objects.create(user=self.other, content='x')
        url = reverse('core:like_post', args=[post.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).json(), {'likes_count': 1, 'liked': True})
        self.assertEqual(self.client.post(url).json(), {'likes_count': 0, 'liked': False})
        self.assertEqual(Like.objects.count(), 0)

    def test_admin_can_delete_any_post_member_cannot(self):
        post = Post.objects.create(user=self.other, content='x')
        url = reverse('core:delete_post', args=[post.id])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url).json(), {'success': True})

    def test_gallery_delete_rejects_get(self):
        photo = PhotoGallery.objects.create(title='t', image='gallery/x.jpg')
        self.client.force_login(self.admin)
        url = reverse('core:delete_gallery_photo', args=[photo.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(PhotoGallery.objects.exists())

    def test_non_admin_redirected_from_admin_gallery(self):
        response = self.client.get(reverse('core:admin_gallery'))
        self.assertRedirects(response, reverse('core:homepage'))

    def test_switch_to_alumni_needs_verification_before_listing(self):
        self.client.post(reverse('core:switch_to_alumni'), {'graduation_year': 2024})
        response = self.client.get(reverse('core:alumni_directory'))
        self.assertEqual(len(response.context['page_obj']), 0)
        self.member.refresh_from_db()
        self.member.is_alumni_verified = True
        self.member.save()
        response = self.client.get(reverse('core:alumni_directory'))
        self.assertEqual(len(response.context['page_obj']), 1)

    def test_directory_bad_filters_do_not_crash(self):
        self.assertEqual(self.client.get(reverse('core:member_directory') + '?batch=abc&department=z').status_code, 200)
        self.assertEqual(self.client.get(reverse('core:alumni_directory') + '?graduation_year=abc').status_code, 200)

    def test_every_page_renders(self):
        """Catches template syntax errors on any page, logged in or not."""
        member_pages = ['homepage', 'about', 'committee', 'committee_directory', 'events', 'gallery',
                        'advisory_panel', 'alumni_directory', 'member_directory', 'dashboard', 'announcements',
                        'inbox', 'view_profile', 'update_profile', 'switch_to_alumni']
        for name in member_pages:
            self.assertEqual(self.client.get(reverse(f'core:{name}')).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('core:member_profile', args=[self.other.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:conversation', args=[self.other.id])).status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('core:admin_gallery')).status_code, 200)
        self.client.logout()
        for url in (reverse('core:login'), reverse('core:register'), reverse('password_reset'), reverse('password_reset_done')):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_public_pages_render(self):
        for name in ('homepage', 'about', 'committee', 'committee_directory', 'events', 'gallery', 'advisory_panel', 'announcements'):
            self.assertEqual(self.client.get(reverse(f'core:{name}')).status_code, 200, name)

    def test_event_rsvp_respects_capacity(self):
        event = Event.objects.create(creator=self.admin, title='Meetup', description='d', venue='v',
                                     date=timezone.now() + timedelta(days=3), capacity=1, status='published')
        url = reverse('core:event_rsvp', args=[event.id])
        self.client.post(url)
        self.client.force_login(self.other)
        self.client.post(url)
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 1)
        self.client.force_login(self.member)
        self.client.post(url)  # cancel
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 0)


class MessagingTests(BaseTestCase):
    """Chat: any approved member can message any other, unless blocked."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.member)
        self.send_url = reverse('core:send_message', args=[self.other.id])
        self.ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def test_anyone_active_can_message_anyone_without_subject(self):
        response = self.client.post(self.send_url, {'body': 'Hello there'}, **self.ajax)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['message']['mine'])
        msg = Message.objects.get()
        self.assertEqual((msg.sender, msg.recipient, msg.subject), (self.member, self.other, ''))

    def test_non_ajax_send_redirects_to_conversation(self):
        response = self.client.post(self.send_url, {'body': 'Hi'})
        self.assertRedirects(response, reverse('core:conversation', args=[self.other.id]))

    def test_send_requires_post_and_body(self):
        self.assertEqual(self.client.get(self.send_url).status_code, 405)
        self.assertEqual(self.client.post(self.send_url, {'body': ''}, **self.ajax).status_code, 400)
        self.assertEqual(self.client.post(self.send_url, {'body': 'x' * 2001}, **self.ajax).status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_cannot_message_self_or_pending_user(self):
        self.client.post(reverse('core:send_message', args=[self.member.id]), {'body': 'me'}, **self.ajax)
        self.client.post(reverse('core:send_message', args=[self.pending.id]), {'body': 'hi'}, **self.ajax)
        self.assertEqual(Message.objects.count(), 0)

    def test_pending_member_cannot_message(self):
        self.client.force_login(self.pending)
        self.client.post(self.send_url, {'body': 'b'})
        self.assertEqual(Message.objects.count(), 0)

    def test_block_stops_messages_both_ways_and_unblock_restores(self):
        Message.objects.create(sender=self.other, recipient=self.member, body='unread')
        self.client.post(reverse('core:toggle_block', args=[self.other.id]))
        self.assertTrue(Block.objects.filter(blocker=self.member, blocked=self.other).exists())
        self.assertFalse(Message.objects.filter(is_read=False).exists())  # blocking clears their unread

        self.assertEqual(self.client.post(self.send_url, {'body': 'hi'}, **self.ajax).status_code, 400)
        self.client.force_login(self.other)
        self.client.post(reverse('core:send_message', args=[self.member.id]), {'body': 'hi'}, **self.ajax)
        self.assertEqual(Message.objects.count(), 1)

        self.client.force_login(self.member)
        self.client.post(reverse('core:toggle_block', args=[self.other.id]))
        self.assertTrue(self.client.post(self.send_url, {'body': 'back'}, **self.ajax).json()['ok'])

    def test_rate_limit(self):
        for i in range(20):
            Message.objects.create(sender=self.member, recipient=self.other, body=str(i))
        self.assertEqual(self.client.post(self.send_url, {'body': 'spam'}, **self.ajax).status_code, 429)

    def test_conversation_marks_read_and_lists_partners(self):
        Message.objects.create(sender=self.other, recipient=self.member, body='Hey, are you coming?')
        response = self.client.get(reverse('core:inbox'))
        self.assertContains(response, 'Hey, are you coming?')
        self.assertEqual(response.context['conversations'][0].unread, 1)

        response = self.client.get(reverse('core:conversation', args=[self.other.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Message.objects.filter(is_read=False).exists())
        self.assertNotContains(response, 'alert-dismissible')  # inbox no longer hijacks flash messages

    def test_poll_returns_new_messages_and_seen_receipts(self):
        mine = Message.objects.create(sender=self.member, recipient=self.other, body='ping')
        Message.objects.create(sender=self.other, recipient=self.member, body='pong')
        url = reverse('core:conversation_poll', args=[self.other.id])
        data = self.client.get(url, {'after': mine.id}).json()
        self.assertEqual([m['body'] for m in data['messages']], ['pong'])
        self.assertEqual(data['unread_total'], 0)
        self.assertEqual(data['seen_upto'], 0)
        mine.is_read = True
        mine.save()
        self.assertEqual(self.client.get(url, {'after': 'junk'}).json()['seen_upto'], mine.id)

    def test_search_finds_active_members_only(self):
        results = self.client.get(reverse('core:messages_search'), {'q': 'u2104'}).json()['results']
        ids = {r['id'] for r in results}
        self.assertIn(self.other.id, ids)
        self.assertNotIn(self.member.id, ids)    # not yourself
        self.assertNotIn(self.pending.id, ids)   # not pending accounts
        Block.objects.create(blocker=self.other, blocked=self.member)
        ids = {r['id'] for r in self.client.get(reverse('core:messages_search'), {'q': 'u2104'}).json()['results']}
        self.assertNotIn(self.other.id, ids)     # not people who blocked you

    def test_messages_are_escaped(self):
        Message.objects.create(sender=self.other, recipient=self.member, body='<script>alert(1)</script>')
        response = self.client.get(reverse('core:conversation', args=[self.other.id]))
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_old_links_redirect_to_conversation(self):
        original = Message.objects.create(sender=self.other, recipient=self.member, subject='Hi', body='b')
        self.assertRedirects(self.client.get(reverse('core:view_message', args=[original.id])),
                             reverse('core:conversation', args=[self.other.id]))
        self.client.post(reverse('core:reply_message', args=[original.id]), {'body': 'ok'})
        self.assertEqual(Message.objects.filter(recipient=self.other).count(), 1)

    def test_unread_endpoint(self):
        Message.objects.create(sender=self.other, recipient=self.member, body='x')
        self.assertEqual(self.client.get(reverse('core:messages_unread')).json(), {'unread': 1, 'notifications': 0})


class ForumTests(BaseTestCase):
    """Boards, sorting and thread pages added with the forum redesign."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.member)
        self.quiet = Post.objects.create(user=self.other, content='Anyone selling a drafter?', category='Help Needed')
        self.busy = Post.objects.create(user=self.member, content='Internship at a telco', category='Job Opportunity', likes_count=3)
        Comment.objects.create(post=self.busy, user=self.other, content='Interested!')

    def test_thread_page_shows_topic_and_replies(self):
        response = self.client.get(reverse('core:post_detail', args=[self.busy.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Internship at a telco')
        self.assertContains(response, 'Interested!')

    def test_thread_page_is_members_only(self):
        self.client.logout()
        response = self.client.get(reverse('core:post_detail', args=[self.busy.id]))
        self.assertEqual(response.status_code, 302)

    def test_reply_from_thread_returns_to_thread(self):
        url = reverse('core:post_detail', args=[self.quiet.id])
        response = self.client.post(reverse('core:add_comment', args=[self.quiet.id]), {'content': 'I have one', 'next': url})
        self.assertTrue(response['Location'].startswith(url))
        self.assertEqual(self.quiet.comments.count(), 1)

    def test_sort_unanswered_and_top(self):
        unanswered = self.client.get(reverse('core:dashboard') + '?sort=unanswered').context['page_obj']
        self.assertEqual([p.id for p in unanswered], [self.quiet.id])
        top = self.client.get(reverse('core:dashboard') + '?sort=top').context['page_obj']
        self.assertEqual(top[0].id, self.busy.id)

    def test_board_counts(self):
        boards = {b['name']: b['topics'] for b in self.client.get(reverse('core:dashboard')).context['boards']}
        self.assertEqual(boards['Help Needed'], 1)
        self.assertEqual(boards['Blood Request'], 0)

    def test_homepage_uses_real_counts(self):
        self.client.logout()
        stats = self.client.get(reverse('core:homepage')).context['stats']
        self.assertEqual(stats['members'], User.objects.filter(status='active').count())
        self.assertEqual(stats['topics'], 2)


class AccessControlTests(BaseTestCase):
    """Who can open what. See the access-control notes at the top of views.py."""

    PUBLIC = ['homepage', 'about', 'events', 'announcements', 'gallery', 'committee',
              'committee_directory', 'advisory_panel', 'alumni_directory', 'login', 'register']
    MEMBERS_ONLY = ['dashboard', 'member_directory', 'inbox', 'switch_to_alumni']

    def test_public_pages_open_to_everyone(self):
        for name in self.PUBLIC:
            self.assertEqual(self.client.get(reverse(f'core:{name}')).status_code, 200, name)

    def test_member_pages_send_visitors_to_login_and_back(self):
        for name in self.MEMBERS_ONLY + ['view_profile', 'update_profile']:
            response = self.client.get(reverse(f'core:{name}'))
            self.assertEqual(response.status_code, 302, name)
            self.assertTrue(response['Location'].startswith(reverse('core:login')), name)
        post = Post.objects.create(user=self.member, content='x')
        self.assertEqual(self.client.get(reverse('core:post_detail', args=[post.id])).status_code, 302)
        self.assertEqual(self.client.get(reverse('core:member_profile', args=[self.member.id])).status_code, 302)

    def test_login_redirect_keeps_the_query_string(self):
        response = self.client.get(reverse('core:dashboard') + '?category=Blood+Request')
        self.assertIn('next=%2Fdashboard%2F%3Fcategory%3DBlood%2BRequest', response['Location'])

    def test_pending_member_can_finish_profile_but_not_enter_forum(self):
        self.client.force_login(self.pending)
        self.assertEqual(self.client.get(reverse('core:view_profile')).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:update_profile')).status_code, 200)
        for name in self.MEMBERS_ONLY:
            response = self.client.get(reverse(f'core:{name}'))
            self.assertRedirects(response, reverse('core:view_profile'), msg_prefix=name)

    def test_pending_member_lands_on_profile_after_login(self):
        self.pending.set_password('pass12345!x')
        self.pending.save()
        response = self.client.post(reverse('core:login'), {'username': self.pending.email, 'password': 'pass12345!x'})
        self.assertRedirects(response, reverse('core:view_profile'))

    def test_deactivated_account_cannot_log_in(self):
        self.member.status = 'inactive'
        self.member.set_password('pass12345!x')
        self.member.save()
        response = self.client.post(reverse('core:login'), {'username': self.member.email, 'password': 'pass12345!x'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_deactivated_session_is_ended(self):
        self.client.force_login(self.member)
        User.objects.filter(pk=self.member.pk).update(status='inactive')
        self.assertRedirects(self.client.get(reverse('core:view_profile')), reverse('core:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('core:logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        self.client.post(reverse('core:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_pages_are_admin_only(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('core:admin_gallery')).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('core:admin_gallery')).status_code, 200)

    def test_advisor_phone_numbers_are_members_only(self):
        phone = '+8801716963388'  # chief advisor, see views.ADVISORS
        self.assertNotContains(self.client.get(reverse('core:advisory_panel')), phone)
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse('core:advisory_panel')), phone)

    def test_cannot_open_chat_with_unapproved_member_by_url(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('core:conversation', args=[self.pending.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('core:conversation', args=[self.other.id])).status_code, 200)


def photo(width=3000, height=2000, name='phone.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (width, height), (30, 60, 120)).save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class LaunchFeatureTests(BaseTestCase):
    """Search, notifications, reply deletion, reports, moderation, donor filters, limits."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.member)
        self.topic = Post.objects.create(user=self.member, content='Where to buy a scientific calculator?', category='Help Needed')

    def reply(self, user, text, post=None):
        self.client.force_login(user)
        return self.client.post(reverse('core:add_comment', args=[(post or self.topic).id]), {'content': text})

    def search(self, q):
        return [p.id for p in self.client.get(reverse('core:dashboard'), {'q': q}).context['page_obj']]

    # search
    def test_search_matches_topics_authors_and_replies(self):
        Post.objects.create(user=self.other, content='Iftar plan for Ramadan')
        Comment.objects.create(post=self.topic, user=self.other, content='Try New Market, Anderkilla')
        self.assertEqual(self.search('calculator'), [self.topic.id])
        self.assertEqual(self.search('anderkilla'), [self.topic.id])     # found through a reply
        self.assertEqual(len(self.search(self.other.full_name)), 1)        # found by author
        self.assertEqual(self.search('zzzz-nothing'), [])

    # notifications
    def test_reply_notifies_author_and_earlier_repliers_once(self):
        self.reply(self.other, 'Try New Market')
        self.assertEqual(Notification.objects.filter(recipient=self.member, is_read=False).count(), 1)
        self.reply(self.admin, 'Or Zahur Hawkers')
        # the author still has ONE unread row for this topic (refreshed); the first replier gets one too
        self.assertEqual(Notification.objects.filter(recipient=self.member, is_read=False).count(), 1)
        self.assertEqual(Notification.objects.get(recipient=self.member).actor, self.admin)
        self.assertEqual(Notification.objects.filter(recipient=self.other).count(), 1)
        self.assertFalse(Notification.objects.filter(recipient=self.admin).exists())  # not for your own reply

    def test_opening_the_topic_marks_it_read(self):
        self.reply(self.other, 'Try New Market')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('core:messages_unread')).json()['notifications'], 1)
        self.client.get(reverse('core:post_detail', args=[self.topic.id]))
        self.assertEqual(self.client.get(reverse('core:messages_unread')).json()['notifications'], 0)

    def test_notifications_page_and_mark_all_read(self):
        self.reply(self.other, 'Try New Market')
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse('core:notifications')), 'replied in your topic')
        self.client.post(reverse('core:notifications'))
        self.assertFalse(Notification.objects.filter(recipient=self.member, is_read=False).exists())

    # deleting replies
    def test_reply_can_be_deleted_by_its_author_or_an_admin_only(self):
        first = Comment.objects.create(post=self.topic, user=self.other, content='one')
        second = Comment.objects.create(post=self.topic, user=self.other, content='two')
        self.client.post(reverse('core:delete_comment', args=[first.id]))           # self.member is not the author
        self.assertTrue(Comment.objects.filter(id=first.id).exists())
        self.client.force_login(self.other)
        self.client.post(reverse('core:delete_comment', args=[first.id]))
        self.assertFalse(Comment.objects.filter(id=first.id).exists())
        self.client.force_login(self.admin)
        self.client.post(reverse('core:delete_comment', args=[second.id]))
        self.assertFalse(Comment.objects.filter(id=second.id).exists())

    # reports and moderation
    def test_report_reaches_admins_and_can_remove_content(self):
        self.client.force_login(self.other)
        self.client.post(reverse('core:report_content'), {'post_id': self.topic.id, 'reason': 'spam', 'note': 'ad'})
        self.client.post(reverse('core:report_content'), {'post_id': self.topic.id, 'reason': 'spam'})  # no duplicates
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(self.client.get(reverse('core:moderation')).status_code, 302)  # members can't open it
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('core:moderation')), 'scientific calculator')
        self.client.post(reverse('core:resolve_report', args=[Report.objects.get().id]), {'action': 'remove'})
        self.assertFalse(Post.objects.filter(id=self.topic.id).exists())

    def test_admin_approves_and_declines_members_in_the_site(self):
        self.client.post(reverse('core:moderate_member', args=[self.pending.id]), {'action': 'approve'})
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'pending')  # a normal member can't approve
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('core:moderation')), self.pending.email)
        self.client.post(reverse('core:moderate_member', args=[self.pending.id]), {'action': 'approve'})
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'active')
        self.assertTrue(self.pending.serial_no)
        self.assertEqual(len(mail.outbox), 1)
        newcomer = make_user('new@example.com', status='pending')
        self.client.post(reverse('core:moderate_member', args=[newcomer.id]), {'action': 'decline'})
        newcomer.refresh_from_db()
        self.assertEqual(newcomer.status, 'inactive')

    # donors
    def test_member_directory_filters_by_blood_group_and_upazila(self):
        User.objects.filter(pk=self.other.pk).update(blood_group='O-', upazila='Ramu')
        User.objects.filter(pk=self.admin.pk).update(blood_group='A+', upazila='Ramu')
        found = self.client.get(reverse('core:member_directory'), {'blood_group': 'O-', 'upazila': 'Ramu'}).context['page_obj']
        self.assertEqual([m.id for m in found], [self.other.id])

    # limits
    def test_login_is_paused_after_repeated_wrong_passwords(self):
        self.client.logout()
        for _ in range(8):
            wrong = self.client.post(reverse('core:login'), {'username': self.member.email, 'password': 'wrong'})
            self.assertEqual(wrong.status_code, 200)
        blocked = self.client.post(reverse('core:login'), {'username': self.member.email, 'password': STRONG_PASSWORD})
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_posting_is_rate_limited(self):
        for i in range(6):
            self.client.post(reverse('core:dashboard'), {'content': f'topic {i}', 'category': 'General'})
        self.client.post(reverse('core:dashboard'), {'content': 'one too many', 'category': 'General'})
        self.assertFalse(Post.objects.filter(content='one too many').exists())

    def test_overlong_topic_and_reply_are_rejected(self):
        self.client.post(reverse('core:dashboard'), {'content': 'x' * 5001, 'category': 'General'})
        self.assertEqual(Post.objects.count(), 1)
        self.client.post(reverse('core:add_comment', args=[self.topic.id]), {'content': 'y' * 2001})
        self.assertEqual(self.topic.comments.count(), 0)

    def test_large_photo_is_shrunk_and_non_images_refused(self):
        self.client.post(reverse('core:dashboard'), {'content': 'with photo', 'category': 'General', 'image': photo()})
        saved = Post.objects.get(content='with photo')
        with Image.open(saved.image.path) as image:
            self.assertLessEqual(max(image.size), 1600)
        fake = SimpleUploadedFile('virus.jpg', b'not really an image', content_type='image/jpeg')
        self.client.post(reverse('core:dashboard'), {'content': 'fake photo', 'category': 'General', 'image': fake})
        self.assertFalse(Post.objects.filter(content='fake photo').exists())

    # pages
    def test_new_public_pages(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('core:guidelines')).status_code, 200)
        self.assertContains(self.client.get(reverse('core:robots_txt')), 'Disallow: /dashboard/')
        self.assertEqual(self.client.get(reverse('core:healthz')).content, b'ok')
        self.assertContains(self.client.get('/no-such-page/'), 'find that page', status_code=404)

    def test_password_change(self):
        response = self.client.post(reverse('password_change'), {
            'old_password': STRONG_PASSWORD, 'new_password1': 'Tide-Pool-9981!', 'new_password2': 'Tide-Pool-9981!'})
        self.assertRedirects(response, reverse('core:view_profile'))
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Tide-Pool-9981!'))
