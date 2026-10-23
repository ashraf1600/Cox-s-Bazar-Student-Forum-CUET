from django.contrib.auth import password_validation
from rest_framework import serializers, exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    User, Department, CommitteeMember, PhotoGallery, Event, EventRegistration,
    Post, Comment, Like, Announcement, Message, is_student_email,
)
from .forms import MIN_BATCH, MAX_BATCH, MIN_GRADUATION_YEAR, max_graduation_year


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']


class PublicUserSerializer(serializers.ModelSerializer):
    """Safe to show to anyone: no email, phone, address, DOB or blood group."""
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    member_type_display = serializers.CharField(source='get_member_type_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'profile_photo', 'member_type', 'member_type_display',
            'batch', 'graduation_year', 'department', 'department_name',
            'company', 'designation', 'linkedin',
        ]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """The logged-in user's own profile. Only personal fields are writable."""
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    member_type_display = serializers.CharField(source='get_member_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'serial_no', 'full_name', 'email', 'member_type', 'member_type_display',
            'is_alumni', 'is_alumni_verified', 'batch', 'graduation_year', 'department', 'department_name',
            'blood_group', 'gender', 'phone', 'address', 'dob', 'profile_photo',
            'upazila', 'company', 'designation', 'work_address', 'linkedin',
            'facebook', 'twitter', 'instagram', 'status', 'status_display', 'role', 'date_joined'
        ]
        read_only_fields = [
            'id', 'serial_no', 'email', 'member_type', 'is_alumni', 'is_alumni_verified',
            'batch', 'graduation_year', 'department', 'status', 'role', 'date_joined',
        ]


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
            'batch': {'required': False, 'allow_null': True, 'min_value': MIN_BATCH, 'max_value': MAX_BATCH},
            'graduation_year': {'required': False, 'allow_null': True, 'min_value': MIN_GRADUATION_YEAR},
            'department': {'required': False, 'allow_null': True},
            'dob': {'required': False, 'allow_null': True},
            'profile_photo': {'required': False, 'allow_null': True},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_graduation_year(self, value):
        if value is not None and value > max_graduation_year():
            raise serializers.ValidationError(f"Graduation year cannot be later than {max_graduation_year()}.")
        return value

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        candidate = User(email=data.get('email', ''), full_name=data.get('full_name', ''))
        try:
            password_validation.validate_password(data['password'], user=candidate)
        except Exception as error:  # django.core.exceptions.ValidationError
            raise serializers.ValidationError({"password": list(getattr(error, 'messages', [str(error)]))})

        member_type = data.get('member_type', 'running_student')
        email = data.get('email', '')

        if member_type == 'running_student':
            if not is_student_email(email):
                raise serializers.ValidationError({"email": "Running students must register with @student.cuet.ac.bd email."})
            if not data.get('batch'):
                raise serializers.ValidationError({"batch": "Batch is required for running students."})
            if not data.get('department'):
                raise serializers.ValidationError({"department": "Department is required for running students."})

        if member_type == 'alumni':
            for field in ('batch', 'department', 'graduation_year'):
                if not data.get(field):
                    raise serializers.ValidationError({field: f"{field.replace('_', ' ').title()} is required for alumni."})

        if member_type == 'advisory' and not data.get('designation'):
            raise serializers.ValidationError({"designation": "Faculty designation is required for Advisory Panel members."})

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        validated_data['status'] = 'pending'
        validated_data['is_alumni'] = validated_data.get('member_type') == 'alumni'
        validated_data['is_alumni_verified'] = False
        email = validated_data.pop('email')
        full_name = validated_data.pop('full_name')
        return User.objects.create_user(email, full_name, password=password, **validated_data)


class ActiveMemberTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Only admin-approved (status='active') members may get API tokens."""
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.status != 'active':
            raise exceptions.AuthenticationFailed('Your account is pending admin approval.', code='not_approved')
        return data


class CommitteeMemberSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )

    class Meta:
        model = CommitteeMember
        fields = ['id', 'user', 'user_id', 'designation', 'session_year', 'order', 'is_current']


class PhotoGallerySerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True, default=None)

    class Meta:
        model = PhotoGallery
        fields = [
            'id', 'title', 'description', 'image', 'uploaded_by',
            'uploaded_by_name', 'category', 'uploaded_date', 'is_featured'
        ]
        read_only_fields = ['uploaded_by', 'uploaded_date']


class EventSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    registered_count = serializers.IntegerField(source='registrations.count', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'creator', 'creator_name', 'title', 'description', 'date',
            'venue', 'cover_image', 'ticket_price', 'capacity', 'registered_count', 'status', 'created_at'
        ]
        read_only_fields = ['creator', 'created_at']


class AnnouncementSerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source='admin.full_name', read_only=True, default=None)

    class Meta:
        model = Announcement
        fields = ['id', 'admin', 'admin_name', 'title', 'content', 'image', 'is_pinned', 'created_at']
        read_only_fields = ['admin', 'created_at']


class CommentSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'post', 'user', 'content', 'created_at']


class PostSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    user_has_liked = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Post
        fields = ['id', 'user', 'content', 'image', 'category', 'likes_count', 'comments', 'user_has_liked', 'created_at']
        read_only_fields = ['likes_count', 'created_at']
