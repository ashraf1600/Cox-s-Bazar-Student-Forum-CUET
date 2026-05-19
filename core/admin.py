from django.contrib import admin
from .models import User, Department, CommitteeMember, Announcement, Post, Comment, Like, Event

# Action to approve pending members
@admin.action(description='Approve selected members')
def approve_members(modeladmin, request, queryset):
    for user in queryset:
        if user.status == 'pending':
            user.status = 'active'
            user.save()
    modeladmin.message_user(request, f'{queryset.count()} members approved.')

class UserAdmin(admin.ModelAdmin):
    list_display = ['serial_no', 'full_name', 'email', 'batch', 'department', 'status', 'role']
    list_filter = ['status', 'role', 'department', 'batch']
    search_fields = ['full_name', 'email', 'serial_no']
    actions = [approve_members]

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
    # Include image field if you have it
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
        if not obj.pk:  # Only when creating a new event
            obj.creator = request.user   # Set creator to the logged-in admin
        super().save_model(request, obj, form, change)

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