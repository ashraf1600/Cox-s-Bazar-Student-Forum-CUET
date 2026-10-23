from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.core.mail import send_mail
from django.urls import reverse
from .models import (
    User, Department, CommitteeMember, Announcement, Post, Comment, Like, Event,
    EventRegistration, PhotoGallery, Message, Block,
)


class CustomUserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'full_name')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


def _notify_approved(request, user):
    login_url = request.build_absolute_uri(reverse('core:login'))
    send_mail(
        subject='Your CSF-CUET membership has been approved',
        message=(
            f"Hi {user.full_name},\n\n"
            f"Your Cox's Bazar Student Forum (CUET) account has been approved.\n"
            f"Your member serial number is {user.serial_no}.\n\n"
            f"You can now log in: {login_url}\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


# Action to approve pending members
@admin.action(description='Approve selected members')
def approve_members(modeladmin, request, queryset):
    approved = 0
    # save() one by one so each member gets a serial number.
    for user in queryset.filter(status='pending'):
        user.status = 'active'
        user.save()
        _notify_approved(request, user)
        approved += 1
    modeladmin.message_user(request, f'{approved} member(s) approved.')


# Action to verify selected alumni
@admin.action(description='Verify selected alumni')
def verify_alumni(modeladmin, request, queryset):
    updated = 0
    for user in queryset:
        if user.member_type == 'alumni' or user.is_alumni:
            user.is_alumni_verified = True
            user.is_alumni = True
            user.member_type = 'alumni'
            user.save()
            updated += 1
    modeladmin.message_user(request, f'{updated} alumni verified successfully.')


# Action to unverify selected alumni
@admin.action(description='Unverify alumni status')
def unverify_alumni(modeladmin, request, queryset):
    updated = queryset.update(is_alumni_verified=False)
    modeladmin.message_user(request, f'{updated} alumni unverified.')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ['serial_no', 'full_name', 'email', 'member_type', 'is_alumni_verified', 'batch', 'graduation_year', 'department', 'status', 'role']
    list_filter = ['member_type', 'is_alumni_verified', 'status', 'role', 'department', 'batch', 'graduation_year']
    search_fields = ['full_name', 'email', 'serial_no']
    list_editable = ['is_alumni_verified']
    ordering = ['-date_joined']
    readonly_fields = ['serial_no', 'date_joined', 'last_login']
    filter_horizontal = ['groups', 'user_permissions']
    actions = [approve_members, verify_alumni, unverify_alumni]

    fieldsets = (
        (None, {'fields': ('email', 'password', 'serial_no')}),
        ('Personal info', {'fields': (
            'full_name', 'profile_photo', 'phone', 'gender', 'blood_group', 'dob', 'address', 'upazila',
        )}),
        ('Academic', {'fields': ('member_type', 'batch', 'department', 'graduation_year', 'is_alumni', 'is_alumni_verified')}),
        ('Professional', {'fields': ('company', 'designation', 'work_address')}),
        ('Social links', {'fields': ('linkedin', 'facebook', 'twitter', 'instagram')}),
        ('Membership', {'fields': ('status', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'member_type', 'status', 'role'),
        }),
    )

class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'designation', 'session_year', 'is_current', 'order']
    list_editable = ['order', 'is_current']
    list_filter = ['is_current', 'session_year']
    search_fields = ['user__full_name', 'designation']
    autocomplete_fields = ['user']

    def get_name(self, obj):
        return obj.user.full_name
    get_name.short_description = 'Name'

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'admin', 'is_pinned', 'created_at')
    list_editable = ('is_pinned',)
    search_fields = ('title', 'content')
    fields = ('title', 'content', 'image', 'is_pinned')

    def save_model(self, request, obj, form, change):
        if not obj.admin_id:
            obj.admin = request.user
        super().save_model(request, obj, form, change)


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    autocomplete_fields = ['user']
    readonly_fields = ['created_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'venue', 'status', 'capacity', 'registered', 'created_at')
    list_filter = ('status', 'date')
    search_fields = ('title', 'description')
    inlines = [EventRegistrationInline]
    fieldsets = (
        (None, {'fields': ('title', 'description', 'cover_image')}),
        ('Event Details', {'fields': ('date', 'venue', 'ticket_price', 'capacity', 'status')}),
    )

    @admin.display(description='Registered')
    def registered(self, obj):
        return obj.registrations.count()

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creator = request.user
        super().save_model(request, obj, form, change)

@admin.register(PhotoGallery)
class PhotoGalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'uploaded_by', 'uploaded_date', 'is_featured')
    list_filter = ('category', 'is_featured', 'uploaded_date')
    search_fields = ('title', 'description')
    list_editable = ('is_featured',)

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'category', 'likes_count', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['content', 'user__full_name', 'user__email']

class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'post', 'created_at']
    search_fields = ['content', 'user__full_name']

class LikeAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'post', 'created_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sender', 'recipient', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['subject', 'body', 'sender__full_name', 'recipient__full_name', 'sender__email', 'recipient__email']
    readonly_fields = ['created_at']


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ['blocker', 'blocked', 'created_at']
    search_fields = ['blocker__full_name', 'blocked__full_name', 'blocker__email', 'blocked__email']
    autocomplete_fields = ['blocker', 'blocked']


# Register remaining models
admin.site.register(Department)
admin.site.register(CommitteeMember, CommitteeMemberAdmin)
admin.site.register(Post, PostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Like, LikeAdmin)
