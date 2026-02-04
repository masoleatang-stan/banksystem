from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone



class Profile(models.Model):
    objects = None
    USER_ROLES = (
        ('customer', 'Customer'),
        ('staff', 'Staff'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=USER_ROLES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Account(models.Model):
    ACCOUNT_TYPES = (
        ('checking', 'Checking'),
        ('savings', 'Savings'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='accounts')
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.owner.user.username} - {self.account_type} Account #{self.id}"


class Transaction(models.Model):
    objects = None
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('transfer', 'Transfer'),
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    # For transfers, store the target account
    target_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.CASCADE,
                                       related_name='incoming_transfers')

    def __str__(self):
        if self.transaction_type == 'transfer' and self.target_account:
            return f"{self.transaction_type.title()} from Account #{self.account.id} to Account #{self.target_account.id} - ${self.amount}"
        return f"{self.transaction_type.title()} on Account #{self.account.id} - ${self.amount}"


class Notification(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True)
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True)
    message = models.TextField()
    action = models.CharField(max_length=255, default="Created")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.receiver.username}: {self.message}"

    def __str__(self):
        return self.message

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    # Optional fields for transfers / auto messages
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    frequency_days = models.IntegerField(null=True, blank=True)
    from_account = models.ForeignKey(
        'Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages_from'
    )
    to_account = models.ForeignKey(
        'Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages_to'
    )
    next_run = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username} at {self.timestamp}"

    class AutoTransfer(models.Model):
        user = models.ForeignKey(User, on_delete=models.CASCADE)
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='from_auto')
    to_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='to_auto')
    amount = models.FloatField()
    frequency_days = models.IntegerField()  # run every X days
    next_run = models.DateTimeField(default=timezone.now)