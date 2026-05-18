from django.contrib import admin
from .models import User, Department, CommitteeMember, Announcement, Post, Comment, Like

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

class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_pinned', 'created_at']
    list_editable = ['is_pinned']

class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'category', 'likes_count', 'created_at']
    list_filter = ['category', 'created_at']

class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'post', 'created_at']

class LikeAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'post', 'created_at']

admin.site.register(User, UserAdmin)
admin.site.register(Department)
admin.site.register(CommitteeMember, CommitteeMemberAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
admin.site.register(Post, PostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Like, LikeAdmin)