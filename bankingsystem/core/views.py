import json

import pandas as pd
import plotly.express as px
import plotly.io as pio
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import transaction as db_transaction
from django.db.models import Count
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_protect

from .forms import AddCustomerForm
from .forms import CustomerMessageForm
from .forms import RegisterForm, AccountForm, DepositForm, WithdrawForm, TransferForm
from .models import (
    Account,
    Notification,
    # Our Django model for Message
    ActivityLog,  # Our Django model for ActivityLog
    Profile,
    Transaction,
)
from .models import Message


class CustomLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return '/dashboard/admin/'
        return '/dashboard/customer/'


@csrf_protect
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Registration successful. Please log in.")
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    """Redirect users to the correct dashboard based on role."""
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return redirect('login')

    if profile.role == 'staff' or request.user.is_superuser:
        return redirect('admin_dashboard')
    elif profile.role == 'customer':
        return redirect('customer_dashboard')
    else:
        return redirect('login')

from django.db.models import Sum

@login_required
def admin_dashboard(request):
    profile = request.user.profile

    # Redirect non-staff users
    if profile.role != 'staff':
        if profile.role == 'customer':
            return redirect('customer_dashboard')
        return redirect('login')

    # Total customers with at least one account
    total_customers = Profile.objects.filter(role='customer', accounts__isnull=False).distinct().count()

    # Total accounts and total balance
    total_accounts = Account.objects.count()
    total_balance = Account.objects.aggregate(total=Sum('balance'))['total'] or 0

    # Transactions today
    today = timezone.now().date()
    transactions_today = Transaction.objects.filter(timestamp__date=today)
    total_transactions_today = transactions_today.count()
    total_amount_today = transactions_today.aggregate(total=Sum('amount'))['total'] or 0

    # Transaction type distribution
    transaction_type_summary = transactions_today.values('transaction_type').annotate(
        total_amount=Sum('amount'),
        count=Count('id')
    )
    transaction_type_summary_dict = {item['transaction_type']: item['total_amount'] for item in transaction_type_summary}

    # Recent transactions
    recent_transactions = Transaction.objects.order_by('-timestamp')[:10]

    # Latest notifications for admin
    notifications = Notification.objects.filter(receiver=request.user).order_by('-timestamp')[:10]

    # Large transactions alert
    large_transaction_threshold = 10000
    large_transactions = Transaction.objects.filter(amount__gte=large_transaction_threshold).order_by('-amount')[:10]

    # Top 5 customers by total balance (only those with accounts)
    top_customers = (
        Profile.objects.filter(role='customer', accounts__isnull=False)
        .annotate(total_balance=Sum('accounts__balance'))
        .order_by('-total_balance')[:5]
    )

    context = {
        'total_customers': total_customers,
        'total_accounts': total_accounts,
        'total_balance': total_balance,
        'total_transactions_today': total_transactions_today,
        'total_amount_today': total_amount_today,
        'transaction_type_summary': transaction_type_summary_dict,
        'transactions': recent_transactions,
        'notifications': notifications,
        'large_transaction_threshold': large_transaction_threshold,
        'large_transactions': large_transactions,
        'top_customers': top_customers,
    }

    return render(request, 'admin/dashboard.html', context)
@login_required
def customer_dashboard(request):
    profile = request.user.profile
    if profile.role != 'customer':
        return redirect('dashboard')

    accounts = profile.accounts.all()
    account_transactions = {
        acc.id: acc.transactions.all().order_by('-timestamp')
        for acc in accounts
    }

    # Fetch notifications for the logged-in customer (most recent first)
    notifications = Notification.objects.filter(receiver=request.user).order_by('-timestamp')[:10]

    balance_chart = None
    if accounts.exists():
        df_bal = pd.DataFrame([
            {'Account': acc.id, 'Balance': float(acc.balance)}
            for acc in accounts
        ])
        fig = px.bar(df_bal, x='Account', y='Balance', title='Your Account Balances')
        balance_chart = mark_safe(pio.to_html(fig, full_html=False))

    # Placeholder for transaction type chart (for future use)
    transaction_type_chart = None
    # In the future, you might aggregate transaction types here and create a chart

    return render(request, 'customer/dashboard.html', {
        'role': 'customer',
        'accounts': accounts,
        'account_transactions': account_transactions,
        'balance_chart': balance_chart,
        'notifications': notifications,
        'transaction_type_chart': transaction_type_chart,
    })


@login_required
def account_detail(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    profile = request.user.profile

    if profile.role == 'customer' and account.owner != profile:
        return redirect('dashboard')

    transactions = account.transactions.all().order_by('timestamp')

    # Calculate balance over time for chart
    balance = 0
    txn_data = []
    for txn in transactions:
        if txn.transaction_type in ['deposit', 'transfer_in']:
            balance += txn.amount
        elif txn.transaction_type in ['withdraw', 'transfer_out']:
            balance -= txn.amount
        # Add a temporary attribute to hold cumulative balance
        txn.cumulative_balance = balance
        txn_data.append(txn)

    return render(request, 'customer/account_detail.html', {
        'account': account,
        'transactions': txn_data,  # use txn_data so template can read cumulative_balance
        'role': profile.role
    })


@login_required
@csrf_protect
def deposit(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    profile = request.user.profile

    # Only allow the owner (customer) or staff to access
    if profile.role == 'customer' and account.owner != profile:
        return redirect('dashboard')
    if profile.role not in ['staff', 'customer']:
        return redirect('dashboard')

    # Use a single line to handle both GET and POST
    form = DepositForm(request.POST or None, account=account, user=request.user)

    if request.method == 'POST' and form.is_valid():
        amount = form.cleaned_data['amount']
        with db_transaction.atomic():
            account.balance += amount
            account.save()
            Transaction.objects.create(
                account=account,
                transaction_type='deposit',
                amount=amount
            )
        messages.success(request, 'Deposit successful')
        return redirect('account_detail', account_id=account.id)

    return render(request, 'customer/deposit.html', {
        'form': form,
        'role': profile.role
    })


@login_required
@csrf_protect
def withdraw(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    profile = request.user.profile

    if profile.role == 'customer' and account.owner != profile:
        return redirect('dashboard')
    if profile.role != 'staff' and profile.role != 'customer':
        return redirect('dashboard')

    if request.method == 'POST':
        form = WithdrawForm(request.POST, account=account)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            if amount > account.balance:
                messages.error(request, 'Insufficient balance')
            else:
                with db_transaction.atomic():
                    account.balance -= amount
                    account.save()
                    Transaction.objects.create(
                        account=account,
                        transaction_type='withdraw',
                        amount=amount
                    )
                messages.success(request, 'Withdrawal successful')
                return redirect('account_detail', account_id=account.id)
    else:
        form = WithdrawForm(account=account)

    return render(request, 'customer/withdraw.html', {'form': form, 'role': profile.role})


@login_required
@csrf_protect
def transfer(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    profile = request.user.profile

    if profile.role == 'customer' and account.owner != profile:
        return redirect('dashboard')

    if request.method == 'POST':
        form = TransferForm(request.POST, account=account)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            target = form.cleaned_data['target_account']

            if target == account:
                messages.error(request, 'Cannot transfer to same account')
            elif amount > account.balance:
                messages.error(request, 'Insufficient balance')
            else:
                with db_transaction.atomic():
                    # 1️⃣ Update balances
                    account.balance -= amount
                    target.balance += amount
                    account.save()
                    target.save()

                    # 2️⃣ Create transaction records
                    txn_out = Transaction.objects.create(
                        account=account,
                        transaction_type='transfer_out',
                        amount=amount
                    )
                    txn_in = Transaction.objects.create(
                        account=target,
                        transaction_type='transfer_in',
                        amount=amount
                    )

                    # 3️⃣ Create notifications
                    Notification.objects.create(
                        sender=account.owner.user,
                        receiver=target.owner.user,
                        message=f"You received ${amount} from {account.owner.user.username}"
                    )
                    Notification.objects.create(
                        sender=account.owner.user,
                        receiver=account.owner.user,
                        message=f"You sent ${amount} to {target.owner.user.username}"
                    )

                    # 4️⃣ Optional: notify all admins
                    admin_profiles = Profile.objects.filter(role='staff')
                    for admin in admin_profiles:
                        Notification.objects.create(
                            sender=account.owner.user,
                            receiver=admin.user,
                            message=f"{account.owner.user.username} transferred ${amount} to {target.owner.user.username}"
                        )

                messages.success(request, 'Transfer successful')
                return redirect('account_detail', account_id=account.id)
    else:
        form = TransferForm(account=account)

    return render(request, 'customer/transfer.html', {'form': form, 'role': profile.role})
@login_required
@csrf_protect
def create_account(request):
    profile = request.user.profile
    if profile.role != 'staff':
        return redirect('dashboard')

    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully')
            return redirect('dashboard')
    else:
        form = AccountForm()

    return render(request, 'admin/create_account.html', {'form': form, 'role': profile.role})


def admin_accounts(request):
    accounts = Account.objects.all()
    return render(request, 'admin/accounts.html', {'accounts': accounts})


def admin_customers(request):
    customers = Profile.objects.filter(role='customer')
    return render(request, 'admin/customers.html', {'customers': customers})


@login_required
def all_accounts(request):
    accounts = Account.objects.all()
    return render(request, 'admin/all_accounts.html', {
        'accounts': accounts
    })


@login_required
def all_customers(request):
    customers = Profile.objects.filter(role='customer')
    return render(request, 'admin/all_customers.html', {
        'customers': customers
    })





@login_required
def add_customer(request):
    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    if request.method == "POST":
        form = AddCustomerForm(request.POST)
        if form.is_valid():
            try:
                # Use the form's save method
                form.save()
                messages.success(request, "Customer added successfully.")
                return redirect('all_customers')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = AddCustomerForm()

    return render(request, 'admin/add_customer.html', {'form': form})


@login_required
def edit_customer(request, user_id):
    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    profile = get_object_or_404(Profile, user__id=user_id)
    user = profile.user

    if request.method == "POST":
        form = AddCustomerForm(request.POST)
        if form.is_valid():
            # Save changes to the existing user
            form.save(user=user)
            messages.success(request, "Customer updated successfully.")
            return redirect('all_customers')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        # Populate form with existing user data
        form = AddCustomerForm(initial={
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })

    return render(request, 'admin/edit_customer.html', {'form': form, 'profile': profile})
@login_required
def delete_customer(request, user_id):
    profile = get_object_or_404(Profile, user__id=user_id)

    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    user = profile.user
    if request.method == "POST":
        user.delete()
        messages.success(request, "Customer deleted successfully.")
        return redirect('all_customers')

    return render(request, 'admin/delete_customer.html', {'profile': profile})

@login_required
def edit_account(request, account_id):
    account = get_object_or_404(Account, id=account_id)

    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    if request.method == "POST":
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "Account updated successfully.")
            return redirect('all_accounts')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = AccountForm(instance=account)

    return render(request, 'admin/edit_account.html', {'form': form, 'account': account})


@login_required
def delete_account(request, account_id):
    account = get_object_or_404(Account, id=account_id)

    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    if request.method == "POST":
        account.delete()
        messages.success(request, "Account deleted successfully.")
        return redirect('all_accounts')

    return render(request, 'admin/delete_account.html', {'account': account})


@login_required
def admin_notifications(request):
    # Only staff/admins should access
    profile = request.user.profile
    if profile.role != 'staff':
        return redirect('dashboard')

    # Fetch all notifications ordered by latest first
    notifications = Notification.objects.all().order_by('-timestamp')

    context = {
        'notifications': notifications
    }
    return render(request, 'admin/notifications.html', context)

@login_required
def pending_accounts(request):
    accounts = Account.objects.filter(status='pending')

    if request.method == 'POST':
        action = request.POST.get('action')
        account_id = request.POST.get('account_id')
        account = get_object_or_404(Account, id=account_id)

        if action == 'approve':
            account.status = 'approved'
        elif action == 'reject':
            account.status = 'rejected'
        account.save()
        return redirect('pending_accounts')

    return render(request, 'admin/pending_accounts.html', {'accounts': accounts})

@login_required
def admin_messages(request):
    profile = request.user.profile
    if profile.role != 'staff':
        return redirect('dashboard')

    # Fetch messages using the Django Message model
    messages_list = Message.objects.order_by('-timestamp')
    context = {
        'messages': messages_list
    }
    return render(request, 'admin/messages.html', context)



@login_required
def admin_transactions(request):
    profile = request.user.profile
    if profile.role != 'staff':
        return redirect('dashboard')

    transactions = Transaction.objects.all().order_by('-timestamp')

    # Filters
    account_id = request.GET.get('account_id')
    customer_username = request.GET.get('customer')
    tx_type = request.GET.get('type')

    if account_id:
        transactions = transactions.filter(account__id=account_id)
    if customer_username:
        transactions = transactions.filter(account__user__username__icontains=customer_username)
    if tx_type:
        transactions = transactions.filter(transaction_type=tx_type)

    context = {
        'transactions': transactions
    }
    return render(request, 'admin/transactions.html', context)



@login_required
def admin_activity_logs(request):
    logs = ActivityLog.objects.select_related('user').order_by('-timestamp')
    return render(request, 'admin/activity_logs.html', {
        'logs': logs
    })

@login_required
@csrf_protect
def spending_insights(request):
    user = request.user
    accounts = Account.objects.filter(owner__user=user)
    transactions = Transaction.objects.filter(account__in=accounts, transaction_type='withdrawal')
    # Aggregate by category (assuming tx.category exists)
    data = transactions.values('category').annotate(total=Sum('amount'))
    chart_data = {
        'labels': [item['category'] for item in data],
        'amounts': [float(item['total']) for item in data]
    }
    return render(request, 'customer/spending_insights.html', {'chart_data': json.dumps(chart_data)})

@login_required
def profile_update(request):
    user = request.user
    if request.method == 'POST':
        user.email = request.POST['email']
        user.first_name = request.POST['first_name']
        user.last_name = request.POST['last_name']
        user.save()
        return redirect('customer_dashboard')
    return render(request, 'customer/profile.html', {'user': user})

@login_required
def customer_messages(request):
    user = request.user

    # Get messages involving this customer
    messages_list = Message.objects.filter(
        receiver=user
    ).order_by('-timestamp')

    if request.method == "POST":
        content = request.POST.get('content')
        # Send message to admin(s)
        admin_users = User.objects.filter(profile__role='staff')
        for admin in admin_users:
            Message.objects.create(sender=user, receiver=admin, content=content)
        return redirect('customer_messages')

    context = {
        'messages': messages_list
    }
    return render(request, 'customer/messages.html', context)


@login_required
def customer_profile(request):
    profile = request.user.profile

    if request.method == "POST":
        # Update personal info
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.email = request.POST.get('email')
        request.user.save()
        profile.role = request.POST.get('role')  # optional, if you want them to see role
        profile.save()
        return redirect('customer_profile')

    context = {
        'user': request.user,
        'profile': profile
    }
    return render(request, 'customer/profile.html', context)




@login_required
def customer_messages(request):
    user = request.user

    if request.method == 'POST':
        form = CustomerMessageForm(request.POST, user=user)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = user
            msg.save()
            return redirect('customer_messages')
    else:
        form = CustomerMessageForm(user=user)

    # Show messages sent or received
    messages_list = Message.objects.filter(sender=user).union(
        Message.objects.filter(receiver=user)
    ).order_by('-timestamp')

    return render(request, 'customer/messages.html', {
        'form': form,
        'messages': messages_list
    })

@login_required
def all_customers(request):
    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    query = request.GET.get('q', '')

    customers = Profile.objects.filter(
        role='customer'
    ).filter(
        Q(user__username__icontains=query) |
        Q(user__email__icontains=query) |
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query)
    )

    context = {
        'customers': customers,
        'query': query,
    }

    return render(request, 'admin/all_customers.html', context)

@login_required
def view_customer(request, user_id):
    if request.user.profile.role != 'staff':
        return redirect('dashboard')

    profile = get_object_or_404(Profile, user__id=user_id, role='customer')
    accounts = Account.objects.filter(owner=profile)

    context = {
        'profile': profile,
        'accounts': accounts,
    }

    return render(request, 'admin/view_customer.html', context)


@login_required
def customer_detail(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, role='customer')
    accounts = profile.accounts.all()  # related_name='accounts'

    context = {
        'profile': profile,
        'accounts': accounts,
    }
    return render(request, 'admin/customer_detail.html', context)