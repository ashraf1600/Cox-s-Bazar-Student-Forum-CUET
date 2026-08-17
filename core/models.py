import re

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

# User Manager
class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
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

    def save(self, *args, **kwargs):
                
                if self.status == 'active':
                    # CASE 1: Student email
                    if self.email and '@student.cuet.ac.bd' in self.email:
                        local_part = self.email.split('@')[0]
                        # local_part example: u2104096
                        if len(local_part) >= 2:
                            # Extract from index 1 to end (2nd to 8th character)
                            student_id = local_part[1:]  # "2104096"
                            # Keep only digits (just in case)
                            student_id = re.sub(r'\D', '', student_id)
                            if student_id:
                                expected_serial = f"CSF{student_id}"
                                # Assign only if not already set correctly
                                if self.serial_no != expected_serial:
                                    self.serial_no = expected_serial

                    # CASE 2: Non-student or extraction failed – auto-increment
                    if not self.serial_no:
                        last_user = User.objects.filter(serial_no__isnull=False).order_by('-id').first()
                        if last_user and last_user.serial_no:
                            # Extract numeric part after "CSF" or "CBSF"
                            # Handle both prefixes
                            num_part = last_user.serial_no
                            if num_part.startswith('CSF'):
                                num_part = num_part[3:]
                            elif num_part.startswith('CBSF'):
                                num_part = num_part[4:]
                            else:
                                num_part = ''
                            if num_part.isdigit():
                                last_num = int(num_part)
                            else:
                                last_num = 0
                            new_num = last_num + 1
                        else:
                            new_num = 1
                        self.serial_no = f"CSF{new_num:05d}"

                super().save(*args, **kwargs)

# CommitteeMember
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
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    image = models.ImageField(upload_to='post_images/', null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='General')
    likes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Post by {self.user.full_name}"

# Comment
class Comment(models.Model):
    id = models.AutoField(primary_key=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
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

class Announcement(models.Model):
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    image = models.ImageField(upload_to='announcements/', null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_messages')
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_read', '-created_at']

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.subject[:30]}"


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
