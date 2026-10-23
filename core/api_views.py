from rest_framework import status, generics, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User, CommitteeMember, PhotoGallery, Event, Post, Like
from .forms import MIN_GRADUATION_YEAR, max_graduation_year
from .serializers import (
    UserSerializer, PublicUserSerializer, RegisterSerializer, CommitteeMemberSerializer,
    PhotoGallerySerializer, EventSerializer, PostSerializer,
    ActiveMemberTokenObtainPairSerializer,
)
from .views import parse_int, verified_alumni


def _is_admin(user):
    return bool(user and user.is_authenticated and (user.role == 'admin' or user.is_superuser))


def _is_active_member(user):
    return bool(user and user.is_authenticated and user.status == 'active')


class IsAdminUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return _is_admin(request.user)


class IsAdminUserCustom(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_admin(request.user)


class IsActiveMember(permissions.BasePermission):
    message = 'Your account is pending admin approval.'

    def has_permission(self, request, view):
        return _is_active_member(request.user)


class IsOwnerOrAdmin(permissions.BasePermission):
    """Anyone allowed by the view may read; only the author (or an admin) may change."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == 'DELETE' and _is_admin(request.user):
            return True
        return obj.user_id == request.user.id


class ActiveMemberTokenObtainPairView(TokenObtainPairView):
    serializer_class = ActiveMemberTokenObtainPairSerializer


# Auth API
class RegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "message": "Registration successful! Please wait for admin approval.",
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


# Profile & Graduation Switch API
class CurrentProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        user = request.user
        wants_alumni = request.data.get('member_type') == 'alumni' or request.data.get('is_alumni') in (True, 'true', '1')

        if wants_alumni and user.member_type != 'alumni':
            if user.status != 'active':
                return Response({"detail": "Your account is pending admin approval."}, status=status.HTTP_403_FORBIDDEN)
            year = parse_int(request.data.get('graduation_year'))
            if year is None or not (MIN_GRADUATION_YEAR <= year <= max_graduation_year()):
                return Response(
                    {"graduation_year": [f"A graduation year between {MIN_GRADUATION_YEAR} and {max_graduation_year()} is required."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Self-declared alumni stay unverified until an admin checks them.
            user.member_type = 'alumni'
            user.is_alumni = True
            user.is_alumni_verified = False
            user.graduation_year = year

        # member_type / role / status / email etc. are read-only on UserSerializer.
        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "message": "Profile updated successfully.",
            "user": serializer.data
        })

    def put(self, request):
        return self.patch(request)


class AdminUserRoleAPIView(APIView):
    permission_classes = [IsAdminUserCustom]

    def patch(self, request, user_id):
        target_user = get_object_or_404(User, id=user_id)
        new_member_type = request.data.get('member_type')
        new_role = request.data.get('role')

        if target_user.is_superuser and not request.user.is_superuser:
            return Response({"detail": "Only a superuser can change another superuser."}, status=status.HTTP_403_FORBIDDEN)

        if new_member_type and new_member_type in dict(User.MEMBER_TYPE_CHOICES):
            target_user.member_type = new_member_type
            target_user.is_alumni = new_member_type == 'alumni'
            if new_member_type == 'alumni':
                # An admin setting the type is itself the verification.
                target_user.is_alumni_verified = True
        if new_role and new_role in dict(User.ROLE_CHOICES):
            target_user.role = new_role
            if not target_user.is_superuser:
                target_user.is_staff = (new_role == 'admin')

        target_user.save()
        return Response({
            "message": f"Updated role/member type for {target_user.full_name}.",
            "user": UserSerializer(target_user).data
        })


# Directory APIs
class AlumniDirectoryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        alumni_members = verified_alumni()

        search_query = request.query_params.get('search', '').strip()
        department_id = parse_int(request.query_params.get('department'))
        batch = parse_int(request.query_params.get('batch'))
        grad_year = parse_int(request.query_params.get('graduation_year'))

        if search_query:
            alumni_members = alumni_members.filter(
                Q(full_name__icontains=search_query) |
                Q(company__icontains=search_query) |
                Q(designation__icontains=search_query)
            )
        if department_id is not None:
            alumni_members = alumni_members.filter(department_id=department_id)
        if batch is not None:
            alumni_members = alumni_members.filter(batch=batch)
        if grad_year is not None:
            alumni_members = alumni_members.filter(graduation_year=grad_year)

        alumni_members = alumni_members.select_related('department').order_by('-graduation_year', '-batch', 'full_name')

        return Response(PublicUserSerializer(alumni_members, many=True).data)


class CommitteeDirectoryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        current_committee = CommitteeMember.objects.filter(is_current=True).select_related('user', 'user__department').order_by('order')
        return Response(CommitteeMemberSerializer(current_committee, many=True).data)


# Photo Gallery ViewSet
class PhotoGalleryViewSet(viewsets.ModelViewSet):
    queryset = PhotoGallery.objects.all()
    serializer_class = PhotoGallerySerializer
    permission_classes = [IsAdminUserOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


# Events & Posts ViewSets
class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdminUserOrReadOnly]

    def get_queryset(self):
        qs = Event.objects.order_by('-date')
        # Admins manage drafts too; everyone else only sees published events.
        if _is_admin(self.request.user):
            return qs
        return qs.filter(status='published')

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class PostViewSet(viewsets.ModelViewSet):
    """Community feed: approved members only (same as the web dashboard)."""
    queryset = Post.objects.select_related('user', 'user__department').prefetch_related('comments', 'comments__user').all()
    serializer_class = PostSerializer
    permission_classes = [IsActiveMember, IsOwnerOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            qs = qs.annotate(user_has_liked=Exists(Like.objects.filter(post=OuterRef('pk'), user=self.request.user)))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
