from rest_framework import status, generics, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Exists, OuterRef, Count
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User, Department, CommitteeMember, PhotoGallery, Event, Post, Comment, Like, Announcement
from .serializers import (
    UserSerializer, RegisterSerializer, CommitteeMemberSerializer,
    PhotoGallerySerializer, EventSerializer, AnnouncementSerializer,
    PostSerializer, CommentSerializer, DepartmentSerializer
)

class IsAdminUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.is_superuser or request.user.is_staff)

class IsAdminUserCustom(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.is_superuser or request.user.is_staff)

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
        data = request.data.copy()
        
        # Self-service switch to Alumni
        if data.get('member_type') == 'alumni' or data.get('is_alumni'):
            user.member_type = 'alumni'
            user.is_alumni = True
            if data.get('graduation_year'):
                user.graduation_year = data.get('graduation_year')

        serializer = UserSerializer(user, data=data, partial=True)
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

        if new_member_type and new_member_type in dict(User.MEMBER_TYPE_CHOICES):
            target_user.member_type = new_member_type
            if new_member_type == 'alumni':
                target_user.is_alumni = True
        if new_role and new_role in dict(User.ROLE_CHOICES):
            target_user.role = new_role
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
        alumni_members = User.objects.filter(
            Q(member_type='alumni') | Q(is_alumni=True),
            status='active'
        )

        search_query = request.query_params.get('search', '').strip()
        department_id = request.query_params.get('department', '').strip()
        batch = request.query_params.get('batch', '').strip()
        grad_year = request.query_params.get('graduation_year', '').strip()

        if search_query:
            alumni_members = alumni_members.filter(
                Q(full_name__icontains=search_query) |
                Q(company__icontains=search_query) |
                Q(designation__icontains=search_query)
            )
        if department_id:
            alumni_members = alumni_members.filter(department_id=department_id)
        if batch:
            alumni_members = alumni_members.filter(batch=batch)
        if grad_year:
            alumni_members = alumni_members.filter(graduation_year=grad_year)

        alumni_members = alumni_members.order_by('-graduation_year', '-batch', 'full_name')

        return Response(UserSerializer(alumni_members, many=True).data)

class CommitteeDirectoryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        current_committee = CommitteeMember.objects.filter(is_current=True).order_by('order')
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
    queryset = Event.objects.filter(status='published').order_by('-date')
    serializer_class = EventSerializer
    permission_classes = [IsAdminUserOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.select_related('user').prefetch_related('comments', 'comments__user').all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            qs = qs.annotate(user_has_liked=Exists(Like.objects.filter(post=OuterRef('pk'), user=self.request.user)))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
