import re

from django.db import models, transaction, IntegrityError
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.functional import cached_property

STUDENT_EMAIL_DOMAIN = '@student.cuet.ac.bd'


def is_student_email(email):
    return bool(email) and email.strip().lower().endswith(STUDENT_EMAIL_DOMAIN)


# User Manager
class UserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        # Case-insensitive login: "Foo@x.com" and "foo@x.com" are the same account.
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})

    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', 'active')
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, full_name, password, **extra_fields)

# Department
class Department(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name
    class Meta:
        ordering = ['name']

# User
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [('member', 'Member'), ('admin', 'Admin')]
    STATUS_CHOICES = [('pending', 'Pending Approval'), ('active', 'Active'), ('inactive', 'Inactive')]
    MEMBER_TYPE_CHOICES = [
        ('running_student', 'Running Student'),
        ('alumni', 'Alumni'),
        ('advisory', 'Advisory Panel'),
    ]
    BLOOD_GROUPS = [('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-')]
    GENDER_CHOICES = [('Male','Male'),('Female','Female'),('Other','Other')]
    UPAZILA_CHOICES = [
        ('Cox\'s Bazar Sadar', "Cox's Bazar Sadar"),
        ('Teknaf', 'Teknaf'),
        ('Ukhiya', 'Ukhiya'),
        ('Chakaria', 'Chakaria'),
        ('Ramu', 'Ramu'),
        ('Pekua', 'Pekua'),
        ('Maheshkhali', 'Maheshkhali'),
        ('Kutubdia', 'Kutubdia'),
        ('Eidgaon', 'Eidgaon'),
        ('Other', 'Other'),
    ]

    id = models.AutoField(primary_key=True)
    serial_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    batch = models.IntegerField(null=True, blank=True)
    graduation_year = models.IntegerField(null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    dob = models.DateField(null=True, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    email_on_reply = models.BooleanField(
        default=False, verbose_name='Email me about replies',
        help_text='One email per topic when someone replies; no more until you open it.')
    upazila = models.CharField(max_length=100, choices=UPAZILA_CHOICES, blank=True)
    linkedin = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    company = models.CharField(max_length=150, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    work_address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    member_type = models.CharField(max_length=20, choices=MEMBER_TYPE_CHOICES, default='running_student')
    is_alumni = models.BooleanField(default=False)
    is_alumni_verified = models.BooleanField(default=False, help_text="Admin-verified alumni status")
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.serial_no or 'Pending'})"

    @property
    def is_full_admin(self):
        """Appointed admins (role = admin) and superusers. Only they can hand out the admin role."""
        return self.is_authenticated and (self.role == 'admin' or self.is_superuser)

    @cached_property
    def is_committee_leader(self):
        """Current President, General Secretary or Assistant General Secretary.

        They run the forum day to day, so they get admin powers for as long as they hold
        the post; moving the committee to "past" removes the access automatically.
        """
        if not self.pk or self.status != 'active':
            return False
        designations = CommitteeMember.objects.filter(user_id=self.pk, is_current=True).values_list('designation', flat=True)
        return any(is_leadership_designation(d) for d in designations)

    @property
    def is_site_admin(self):
        """Can use the admin panel: approve members, post events and notices, moderate."""
        return self.is_authenticated and (self.is_full_admin or self.is_committee_leader)

    @property
    def is_active_member(self):
        return self.status == 'active'

    # Non-student serials are always CSF + exactly 5 digits (CBSF is the legacy prefix).
    # Student serials are CSF + the 7-digit student ID, so the two ranges never overlap.
    NON_STUDENT_SERIAL_RE = r'^(CSF|CBSF)[0-9]{5}$'

    def _student_serial(self):
        if not is_student_email(self.email):
            return None
        local_part = self.email.split('@')[0]          # e.g. u2104096
        student_id = re.sub(r'\D', '', local_part[1:])  # "2104096"
        return f"CSF{student_id}" if student_id else None

    @classmethod
    def _next_non_student_serial(cls):
        serials = cls.objects.filter(serial_no__regex=cls.NON_STUDENT_SERIAL_RE).values_list('serial_no', flat=True)
        last_num = max((int(re.sub(r'\D', '', s)) for s in serials), default=0)
        return f"CSF{last_num + 1:05d}"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        generated = False
        if self.status == 'active':
            student_serial = self._student_serial()
            if student_serial:
                self.serial_no = student_serial
            elif not self.serial_no:
                self.serial_no = self._next_non_student_serial()
                generated = True

        if not generated:
            return super().save(*args, **kwargs)

        # Two approvals at the same moment can pick the same number; retry with the next one.
        for attempt in range(5):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                clash = User.objects.filter(serial_no=self.serial_no).exclude(pk=self.pk).exists()
                if not clash or attempt == 4:
                    raise
                self.serial_no = self._next_non_student_serial()

# CommitteeMember
# Committee posts that come with admin access, in every spelling people actually type.
LEADERSHIP_DESIGNATIONS = {
    'president',
    'general secretary', 'gs', 'gen secretary', 'general sec',
    'assistant general secretary', 'ags', 'asst general secretary', 'assistant gs', 'asst gs',
}
STANDARD_DESIGNATIONS = [
    'President', 'Vice President', 'General Secretary', 'Assistant General Secretary',
    'Organizing Secretary', 'Treasurer', 'Office Secretary', 'Publicity Secretary',
    'Cultural Secretary', 'Sports Secretary', 'IT Secretary', 'Executive Member',
]


def is_leadership_designation(designation):
    # 'G.S.' -> 'gs', 'Asst. General-Secretary' -> 'asst general secretary'
    normalized = ' '.join((designation or '').lower().replace('.', '').replace('-', ' ').split())
    return normalized in LEADERSHIP_DESIGNATIONS


class CommitteeMember(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='committee_roles')
    designation = models.CharField(max_length=100)
    session_year = models.CharField(max_length=20)
    order = models.IntegerField(default=0)
    is_current = models.BooleanField(default=True)
    # Optional: keep name field for simplicity? Better to use user.full_name in admin.
    # To avoid admin error, we'll add a property or use user__full_name in list_display.
    def __str__(self):
        return f"{self.user.full_name} - {self.designation}"

    @property
    def grants_admin(self):
        return self.is_current and is_leadership_designation(self.designation)

    class Meta:
        ordering = ['order', 'designation']

# Post
class Post(models.Model):
    CATEGORY_CHOICES = [
    ('General', 'General'),
    ('Help Needed', 'Help Needed'),
    ('Blood Request', 'Blood Request'),
    ('Job Opportunity', 'Job Opportunity'),
    ('Event', 'Event'),
    ('Tuition Offer', 'Tuition Offer'),
    ('Success Story', 'Success Story'),
    ('Sports', 'Sports'),
    ('Celebrations', 'Celebrations'),
]
    # CATEGORY_CHOICES = [
    #     ('General', 'General'),
    #     ('Help Needed', 'Help Needed'),
    #     ('Blood Request', 'Blood Request'),
    #     ('Job Opportunity', 'Job Opportunity'),
    #     ('Event', 'Event'),
    # ]
    MAX_LENGTH = 5000

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    image = models.ImageField(upload_to='post_images/', null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='General')
    likes_count = models.IntegerField(default=0)
    is_pinned = models.BooleanField(default=False, help_text='Pinned topics stay at the top of "Latest".')
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Post by {self.user.full_name}"

# Comment
class Comment(models.Model):
    id = models.AutoField(primary_key=True)
    MAX_LENGTH = 2000

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['created_at']
    def __str__(self):
        return f"Comment by {self.user.full_name} on {self.post}"

# Like
class Like(models.Model):
    id = models.AutoField(primary_key=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ['post', 'user']
    def __str__(self):
        return f"Like by {self.user.full_name}"

# Announcement
class Event(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    cover_image = models.ImageField(upload_to='events/', null=True, blank=True)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    capacity = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=[('draft','Draft'),('published','Published')], default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title

    @property
    def seats_left(self):
        """None means unlimited capacity (capacity = 0)."""
        if not self.capacity:
            return None
        return max(self.capacity - self.registrations.count(), 0)


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_registrations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'user']
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.full_name} → {self.event.title}"


class Announcement(models.Model):
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    image = models.ImageField(upload_to='announcements/', null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title


class MessageQuerySet(models.QuerySet):
    def between(self, user_a, user_b):
        """All messages exchanged between two members, in either direction."""
        return self.filter(
            models.Q(sender=user_a, recipient=user_b) | models.Q(sender=user_b, recipient=user_a)
        )


class Message(models.Model):
    MAX_BODY_LENGTH = 2000

    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_messages')
    # Chat messages have no subject; older email-style messages keep theirs.
    subject = models.CharField(max_length=200, blank=True, default='')
    body = models.TextField(max_length=MAX_BODY_LENGTH)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MessageQuerySet.as_manager()

    class Meta:
        ordering = ['is_read', '-created_at']
        indexes = [
            models.Index(fields=['sender', 'recipient', 'created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {(self.subject or self.body)[:30]}"


class Block(models.Model):
    """`blocker` no longer receives messages from `blocked` (and can't message them either)."""
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks_made')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['blocker', 'blocked']

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"

    @classmethod
    def exists_between(cls, user_a, user_b):
        return cls.objects.filter(
            models.Q(blocker=user_a, blocked=user_b) | models.Q(blocker=user_b, blocked=user_a)
        ).exists()


class PhotoGallery(models.Model):
    CATEGORY_CHOICES = [
        ('Event', 'Event'),
        ('Workshop', 'Workshop'),
        ('Social', 'Social'),
        ('Sports', 'Sports'),
        ('Academic', 'Academic'),
        ('Other', 'Other'),
    ]
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='gallery/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Event')
    uploaded_date = models.DateTimeField(auto_now_add=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ['-uploaded_date']

    def __str__(self):
        return self.title


class Notification(models.Model):
    """Tells a member that someone replied in a topic they started or joined.

    One unread row per (recipient, post): further replies refresh it instead of piling up.
    """
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='notifications')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read', '-created_at'])]

    def __str__(self):
        return f"{self.actor} replied in topic {self.post_id} → {self.recipient}"

    @classmethod
    def notify_reply(cls, comment):
        """Notify the topic's author and everyone who replied earlier (except the replier).

        Returns the members who had no unread alert for this topic yet, i.e. the ones who
        should get an email if they asked for one (at most one email per topic until read).
        """
        post = comment.post
        recipient_ids = set(post.comments.exclude(pk=comment.pk).values_list('user_id', flat=True))
        recipient_ids.add(post.user_id)
        recipient_ids.discard(comment.user_id)
        newly_alerted = []
        for user in User.objects.filter(id__in=recipient_ids, status='active'):
            updated = cls.objects.filter(recipient=user, post=post, is_read=False).update(
                actor=comment.user, comment=comment, created_at=timezone.now())
            if not updated:
                cls.objects.create(recipient=user, actor=comment.user, post=post, comment=comment)
                newly_alerted.append(user)
        return newly_alerted


class Report(models.Model):
    """A member flags a topic or a reply for the admins to look at."""
    REASON_CHOICES = [
        ('spam', 'Spam or advertising'),
        ('abuse', 'Harassment or abusive language'),
        ('misinformation', 'False or misleading'),
        ('wrong_board', 'Posted on the wrong board'),
        ('other', 'Something else'),
    ]
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='other')
    note = models.CharField(max_length=500, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_resolved', '-created_at']
        indexes = [models.Index(fields=['is_resolved', '-created_at'])]

    def __str__(self):
        return f"Report by {self.reporter} on {'reply' if self.comment_id else 'topic'} ({self.get_reason_display()})"

    @property
    def target_author(self):
        return self.comment.user if self.comment_id else self.post.user

    @property
    def target_text(self):
        return self.comment.content if self.comment_id else self.post.content

    @property
    def thread_id(self):
        return self.comment.post_id if self.comment_id else self.post_id
