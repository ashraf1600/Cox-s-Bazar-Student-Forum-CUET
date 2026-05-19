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
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.serial_no or 'Pending'})"

    def save(self, *args, **kwargs):
        if self.status == 'active' and not self.serial_no:
            last_user = User.objects.filter(serial_no__isnull=False).order_by('-id').first()
            if last_user and last_user.serial_no:
                last_num = int(last_user.serial_no.replace('CBSF', ''))
                new_num = last_num + 1
            else:
                new_num = 1
            self.serial_no = f"CBSF{new_num:05d}"
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
    ]
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