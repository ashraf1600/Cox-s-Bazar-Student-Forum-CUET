from django import forms
from .models import User, Department, Post, Comment
from django.contrib.auth.forms import AuthenticationForm

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    profile_photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
    upazila = forms.ChoiceField(
        choices=[('', 'Select Upazila')] + User.UPAZILA_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'batch', 'department', 'blood_group', 
                  'gender', 'phone', 'address', 'dob', 'upazila', 'profile_photo']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'batch': forms.NumberInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'upazila': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_order = [
            'full_name', 'email', 'batch', 'department', 'blood_group', 
            'gender', 'phone', 'address', 'dob', 'upazila', 'profile_photo',
            'password', 'confirm_password'
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # We accept both students and alumni. Alumni may use their personal/current email domains.
        # Pending accounts are manually verified and approved by the admin committee.
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match')
        return cleaned_data

# LoginForm, PostForm, CommentForm remain unchanged# forms.py
from django import forms
from .models import User

class ProfileUpdateForm(forms.ModelForm):
    # upazila already has choices from the model; we only need to add a blank option.
    upazila = forms.ChoiceField(
        choices=[('', 'Select Upazila')] + User.UPAZILA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        # Exclude fields that should not be changed after account creation
        exclude = ['email', 'batch', 'department', 'serial_no', 'status', 'role', 
                   'date_joined', 'is_active', 'is_staff', 'password', 'last_login']
        fields = [
            'full_name', 'phone', 'address', 'dob', 'upazila', 'blood_group', 'gender',
            'profile_photo', 'linkedin', 'facebook', 'twitter', 'instagram',
            'company', 'designation', 'work_address'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'profile_photo': forms.FileInput(attrs={'class': 'form-control'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/in/username'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/username'}),
            'twitter': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://twitter.com/username'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://instagram.com/username'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'work_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'full_name': 'Full Name',
            'dob': 'Date of Birth',
            'upazila': 'Upazila (Cox\'s Bazar)',
            'blood_group': 'Blood Group',
            'profile_photo': 'Profile Picture',
            'linkedin': 'LinkedIn URL',
            'facebook': 'Facebook URL',
            'twitter': 'Twitter/X URL',
            'instagram': 'Instagram URL',
            'company': 'Current Company',
            'designation': 'Designation',
            'work_address': 'Work Address',
        }

class LoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image', 'category']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': "What's on your mind?"}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }
        
class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Write a comment...'}),
        }


        