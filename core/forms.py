from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.utils import timezone

from .images import AVATAR_MAX_SIDE, COVER_MAX_SIDE, GALLERY_MAX_SIDE, POST_MAX_SIDE, prepare_image
from .models import (
    User, Department, Post, Comment, Message, PhotoGallery, Report, Event, Announcement, CommitteeMember,
    is_student_email,
)

MIN_BATCH, MAX_BATCH = 1, 99
MIN_GRADUATION_YEAR = 1968  # CUET was founded in 1968


def max_graduation_year():
    return timezone.now().year + 6


def validate_batch(form, batch):
    if batch is not None and not (MIN_BATCH <= batch <= MAX_BATCH):
        form.add_error('batch', f'Batch must be between {MIN_BATCH} and {MAX_BATCH} (e.g. 21).')


def validate_graduation_year(form, year):
    if year is not None and not (MIN_GRADUATION_YEAR <= year <= max_graduation_year()):
        form.add_error('graduation_year', f'Graduation year must be between {MIN_GRADUATION_YEAR} and {max_graduation_year()}.')

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
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Assistant Professor, Dept of CE'}),
        }
        labels = {
            'full_name': 'Full name',
            'member_type': 'I am a',
            'graduation_year': 'Graduation year',
            'blood_group': 'Blood group',
            'phone': 'Phone number',
            'dob': 'Date of birth',
            'upazila': 'Home upazila',
            'designation': 'Faculty designation',
            'profile_photo': 'Profile photo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['confirm_password'].label = 'Confirm password'
        self.fields['upazila'].label = 'Home upazila'
        self.fields['department'].empty_label = 'Select department'
        self.fields['blood_group'].choices = [('', 'Select blood group')] + User.BLOOD_GROUPS
        self.fields['gender'].choices = [('', 'Select gender')] + User.GENDER_CHOICES
        self.fields['email'].widget.attrs['placeholder'] = 'u2104XXX@student.cuet.ac.bd'
        self.fields['full_name'].widget.attrs['placeholder'] = 'Your full name'
        self.fields['phone'].widget.attrs['placeholder'] = '01XXXXXXXXX'
        self.fields['password'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['confirm_password'].widget.attrs['autocomplete'] = 'new-password'

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email is already registered.')
        return email

    def clean_profile_photo(self):
        return prepare_image(self.cleaned_data.get('profile_photo'), AVATAR_MAX_SIDE)

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
            self.add_error('confirm_password', 'Passwords do not match.')
        elif password:
            candidate = User(email=email or '', full_name=cleaned_data.get('full_name') or '')
            try:
                password_validation.validate_password(password, user=candidate)
            except forms.ValidationError as error:
                self.add_error('password', error)

        validate_batch(self, batch)
        validate_graduation_year(self, graduation_year)

        if member_type == 'running_student':
            if email and not is_student_email(email):
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
        # Only these fields are user-editable; email, batch, department, status, role etc. are not.
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

    def clean_profile_photo(self):
        return prepare_image(self.cleaned_data.get('profile_photo'), AVATAR_MAX_SIDE)

class LoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        # Pending accounts may sign in (to finish their profile); deactivated ones may not.
        if user.status == 'inactive':
            raise forms.ValidationError(
                'This account has been deactivated. Contact the committee if you think this is a mistake.',
                code='inactive',
            )


class PostForm(forms.ModelForm):
    content = forms.CharField(
        max_length=Post.MAX_LENGTH, strip=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': "What's on your mind?"}),
        error_messages={'required': 'Write something before posting.',
                        'max_length': f'Topics can be up to {Post.MAX_LENGTH} characters.'},
    )

    class Meta:
        model = Post
        fields = ['content', 'image', 'category']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_image(self):
        return prepare_image(self.cleaned_data.get('image'), POST_MAX_SIDE)


class CommentForm(forms.ModelForm):
    content = forms.CharField(
        max_length=Comment.MAX_LENGTH, strip=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        error_messages={'max_length': f'Replies can be up to {Comment.MAX_LENGTH} characters.'},
    )

    class Meta:
        model = Comment
        fields = ['content']


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'note']



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
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Photo Title (Applied to all if multiple)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional photo description...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_image(self):
        return prepare_image(self.cleaned_data.get('image'), GALLERY_MAX_SIDE)


class SwitchToAlumniForm(forms.Form):
    graduation_year = forms.IntegerField(
        required=True,
        min_value=MIN_GRADUATION_YEAR,
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

    def clean_graduation_year(self):
        year = self.cleaned_data['graduation_year']
        if year > max_graduation_year():
            raise forms.ValidationError(f'Graduation year cannot be later than {max_graduation_year()}.')
        return year


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'you@example.com', 'autofocus': True})


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['old_password'].label = 'Current password'
        self.fields['new_password1'].label = 'New password'
        self.fields['new_password1'].help_text = 'At least 8 characters. Avoid common passwords or ones close to your name or email.'
        self.fields['new_password2'].label = 'New password again'


# ── Admin panel forms ─────────────────────────────────────────────────────

class EventForm(forms.ModelForm):
    date = forms.DateTimeField(
        label='Date and time',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
    )

    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'venue', 'cover_image', 'ticket_price', 'capacity', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Annual Iftar Party 2027'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6,
                                                 'placeholder': 'What is happening, who it is for, what to bring, who to contact.'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CUET Auditorium'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'ticket_price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '1'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {'cover_image': 'Cover photo', 'ticket_price': 'Entry fee (Tk)', 'capacity': 'Seats', 'status': 'Visibility'}
        help_texts = {
            'ticket_price': 'Leave 0 for a free event.',
            'capacity': 'Leave 0 for unlimited seats.',
            'status': 'Drafts are visible to admins only. Published events appear on the Events page.',
        }

    def clean_cover_image(self):
        return prepare_image(self.cleaned_data.get('cover_image'), COVER_MAX_SIDE)

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity') or 0
        if capacity < 0:
            raise forms.ValidationError('Seats cannot be negative.')
        return capacity

    def clean_ticket_price(self):
        price = self.cleaned_data.get('ticket_price') or 0
        if price < 0:
            raise forms.ValidationError('The entry fee cannot be negative.')
        return price


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'image', 'is_pinned']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Membership fee collection starts Sunday'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 7}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {'content': 'Notice', 'image': 'Image (optional)', 'is_pinned': 'Pin to the top'}

    def clean_image(self):
        return prepare_image(self.cleaned_data.get('image'), COVER_MAX_SIDE)


class CommitteeMemberForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(status='active').order_by('full_name'),
        label='Member', empty_label='Choose a member',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = CommitteeMember
        fields = ['user', 'designation', 'session_year', 'order', 'is_current']
        widgets = {
            'designation': forms.TextInput(attrs={'class': 'form-control', 'list': 'designationOptions', 'placeholder': 'e.g. General Secretary'}),
            'session_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026-27'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {'designation': 'Post', 'session_year': 'Session', 'order': 'Position in the list', 'is_current': 'Part of the current committee'}
        help_texts = {'order': 'Lower numbers come first. President is usually 1.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].label_from_instance = lambda u: f"{u.full_name} ({u.email})"

    def clean_designation(self):
        return ' '.join(self.cleaned_data['designation'].split())

    def clean_session_year(self):
        return self.cleaned_data['session_year'].strip()
