from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import Account, Profile
from .models import Message

# Deposit, Withdraw, Transfer forms
class DepositForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01, label='Deposit Amount')

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)


class WithdrawForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01, label='Withdraw Amount')

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)


class TransferForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01, label='Transfer Amount')
    target_account = forms.ModelChoiceField(queryset=Account.objects.all(), label='Target Account')

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.account:
            self.fields['target_account'].queryset = Account.objects.exclude(id=self.account.id)


# User registration
class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


# Account management
class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['owner', 'account_type', 'balance']
        widgets = {
            'owner': forms.Select(),
        }


# Customer addition
def make_password(param):
    pass


class AddCustomerForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if password and password != confirm:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

    def save(self, user=None):
        """
        Creates a new customer if 'user' is None, otherwise updates the existing user.
        Automatically creates or updates the Profile.
        """
        data = self.cleaned_data

        if user is None:
            # CREATE NEW USER
            user = User.objects.create(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                password=make_password(data['password'])  # hash password
            )
            # Create profile for new customer
            Profile.objects.get_or_create(user=user, defaults={'role': 'customer'})

        else:
            # UPDATE EXISTING USER
            user.username = data['username']
            user.email = data['email']
            user.first_name = data['first_name']
            user.last_name = data['last_name']

            # Update password only if provided
            if data.get('password'):
                user.set_password(data['password'])

            user.save()

            # Ensure profile exists
            Profile.objects.get_or_create(user=user, defaults={'role': 'customer'})

        return user

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['account_type', 'balance', 'owner']
        widgets = {
            'balance': forms.NumberInput(attrs={'step': 0.01}),
        }


class CustomerMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'receiver']  # only content and receiver

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # Only allow sending to admin users
            self.fields['receiver'].queryset = User.objects.filter(is_staff=True)
            self.fields['receiver'].label = "Send To Admin"