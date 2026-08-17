from django.contrib import admin
from .models import User, Department, CommitteeMember, Announcement, Post, Comment, Like, Event, PhotoGallery

# Action to approve pending members
@admin.action(description='Approve selected members')
def approve_members(modeladmin, request, queryset):
    for user in queryset:
        if user.status == 'pending':
            user.status = 'active'
            user.save()
    modeladmin.message_user(request, f'{queryset.count()} members approved.')


# Action to verify selected alumni
@admin.action(description='Verify selected alumni')
def verify_alumni(modeladmin, request, queryset):
    updated = 0
    for user in queryset:
        if user.member_type == 'alumni' or user.is_alumni:
            user.is_alumni_verified = True
            if user.member_type != 'alumni':
                user.member_type = 'alumni'
            user.save()
            updated += 1
    modeladmin.message_user(request, f'{updated} alumni verified successfully.')


# Action to unverify selected alumni
@admin.action(description='Unverify alumni status')
def unverify_alumni(modeladmin, request, queryset):
    updated = queryset.update(is_alumni_verified=False)
    modeladmin.message_user(request, f'{updated} alumni unverified.')


class UserAdmin(admin.ModelAdmin):
    list_display = ['serial_no', 'full_name', 'email', 'member_type', 'is_alumni_verified', 'batch', 'graduation_year', 'department', 'status', 'role']
    list_filter = ['member_type', 'is_alumni_verified', 'status', 'role', 'department', 'batch', 'graduation_year']
    search_fields = ['full_name', 'email', 'serial_no']
    list_editable = ['is_alumni_verified']
    actions = [approve_members, verify_alumni, unverify_alumni]

class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'designation', 'session_year', 'is_current', 'order']
    list_editable = ['order', 'is_current']
    list_filter = ['is_current', 'session_year']
    search_fields = ['user__full_name', 'designation']
    
    def get_name(self, obj):
        return obj.user.full_name
    get_name.short_description = 'Name'

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_pinned', 'created_at')
    list_editable = ('is_pinned',)
    search_fields = ('title', 'content')
    fields = ('title', 'content', 'image', 'is_pinned')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'venue', 'status', 'created_at')
    list_filter = ('status', 'date')
    search_fields = ('title', 'description')
    fieldsets = (
        (None, {'fields': ('title', 'description', 'cover_image')}),
        ('Event Details', {'fields': ('date', 'venue', 'ticket_price', 'capacity', 'status')}),
    )

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

class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'category', 'likes_count', 'created_at']
    list_filter = ['category', 'created_at']

class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'post', 'created_at']

class LikeAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'post', 'created_at']

# Register all models
admin.site.register(User, UserAdmin)
admin.site.register(Department)
admin.site.register(CommitteeMember, CommitteeMemberAdmin)
admin.site.register(Post, PostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Like, LikeAdmin)
