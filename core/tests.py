import shutil
import tempfile
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import User, Department, Post, Comment, Like, Message, Block, Event, EventRegistration, PhotoGallery

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
        self.assertEqual(self.client.get(reverse('core:messages_unread')).json(), {'unread': 1})


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
