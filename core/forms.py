from django import forms
from .models import User, Department, Post, Comment, Message, PhotoGallery
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
        fields = ['full_name', 'email', 'member_type', 'batch', 'graduation_year', 'department', 'blood_group', 
                  'gender', 'phone', 'address', 'dob', 'upazila', 'designation', 'profile_photo']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'member_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_member_type'}),
            'batch': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Batch (e.g. 17)'}),
            'graduation_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Graduation Year (e.g. 2022)'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Faculty Designation (for Advisory Panel)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_order = [
            'full_name', 'email', 'member_type', 'batch', 'graduation_year', 'department', 'blood_group', 
            'gender', 'phone', 'address', 'dob', 'upazila', 'designation', 'profile_photo',
            'password', 'confirm_password'
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email is already registered.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        member_type = cleaned_data.get('member_type')
        email = cleaned_data.get('email')
        batch = cleaned_data.get('batch')
        department = cleaned_data.get('department')
        graduation_year = cleaned_data.get('graduation_year')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')

        if member_type == 'running_student':
            if email and '@student.cuet.ac.bd' not in email.lower():
                self.add_error('email', 'Running students must register with their @student.cuet.ac.bd email address.')
            if not batch:
                self.add_error('batch', 'Batch is required for running students.')
            if not department:
                self.add_error('department', 'Department is required for running students.')

        elif member_type == 'alumni':
            if not batch:
                self.add_error('batch', 'Batch is required for alumni.')
            if not department:
                self.add_error('department', 'Department is required for alumni.')
            if not graduation_year:
                self.add_error('graduation_year', 'Graduation Year is required for alumni.')

        elif member_type == 'advisory':
            designation = cleaned_data.get('designation')
            if not designation:
                self.add_error('designation', 'Faculty designation is required for Advisory Panel members.')

        return cleaned_data


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



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['subject', 'body']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Your message...'}),
        }


class PhotoGalleryForm(forms.ModelForm):
    class Meta:
        model = PhotoGallery
        fields = ['title', 'description', 'image', 'category', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Photo Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional photo description...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SwitchToAlumniForm(forms.Form):
    graduation_year = forms.IntegerField(
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2024'}),
        label='Graduation Year'
    )
    company = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Current Company / Organization'}),
        label='Current Company'
    )
    designation = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Designation / Job Title'}),
        label='Designation'
    )