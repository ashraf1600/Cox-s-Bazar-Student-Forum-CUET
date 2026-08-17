from rest_framework import serializers
from .models import User, Department, CommitteeMember, PhotoGallery, Event, Post, Comment, Like, Announcement, Message

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']

class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    member_type_display = serializers.CharField(source='get_member_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'serial_no', 'full_name', 'email', 'member_type', 'member_type_display',
            'is_alumni', 'batch', 'graduation_year', 'department', 'department_name',
            'blood_group', 'gender', 'phone', 'address', 'dob', 'profile_photo',
            'upazila', 'company', 'designation', 'work_address', 'linkedin',
            'facebook', 'twitter', 'instagram', 'status', 'status_display', 'role', 'date_joined'
        ]
        read_only_fields = ['id', 'serial_no', 'status', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'password', 'confirm_password', 'member_type',
            'batch', 'graduation_year', 'department', 'blood_group', 'gender',
            'phone', 'address', 'dob', 'upazila', 'designation', 'profile_photo'
        ]
        extra_kwargs = {
            'blood_group': {'required': False, 'allow_blank': True},
            'gender': {'required': False, 'allow_blank': True},
            'phone': {'required': False, 'allow_blank': True},
            'address': {'required': False, 'allow_blank': True},
            'upazila': {'required': False, 'allow_blank': True},
            'batch': {'required': False, 'allow_null': True},
            'graduation_year': {'required': False, 'allow_null': True},
            'department': {'required': False, 'allow_null': True},
            'dob': {'required': False, 'allow_null': True},
            'profile_photo': {'required': False, 'allow_null': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"password": "Passwords do not match."})

        member_type = data.get('member_type', 'running_student')
        email = data.get('email', '')

        if member_type == 'running_student' and '@student.cuet.ac.bd' not in email.lower():
            raise serializers.ValidationError({"email": "Running students must register with @student.cuet.ac.bd email."})

        if member_type == 'alumni' and not data.get('graduation_year'):
            raise serializers.ValidationError({"graduation_year": "Graduation Year is required for alumni."})

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        validated_data['status'] = 'pending'
        if validated_data.get('member_type') == 'alumni':
            validated_data['is_alumni'] = True
        user = User.objects.create_user(password=password, **validated_data)
        return user

class CommitteeMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )

    class Meta:
        model = CommitteeMember
        fields = ['id', 'user', 'user_id', 'designation', 'session_year', 'order', 'is_current']

class PhotoGallerySerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = PhotoGallery
        fields = [
            'id', 'title', 'description', 'image', 'uploaded_by',
            'uploaded_by_name', 'category', 'uploaded_date', 'is_featured'
        ]

class EventSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'creator', 'creator_name', 'title', 'description', 'date',
            'venue', 'cover_image', 'ticket_price', 'capacity', 'status', 'created_at'
        ]

class AnnouncementSerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source='admin.full_name', read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'admin', 'admin_name', 'title', 'content', 'image', 'is_pinned', 'created_at']

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'post', 'user', 'content', 'created_at']

class PostSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    user_has_liked = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Post
        fields = ['id', 'user', 'content', 'image', 'category', 'likes_count', 'comments', 'user_has_liked', 'created_at']
