from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .views import (
    dashboard, admin_dashboard, customer_dashboard,
    account_detail, deposit, withdraw, transfer,
    register
)

urlpatterns = [
    # Auth
    path('', LoginView.as_view(template_name='registration/login.html'), name='home'),
    path('register/', register, name='register'),
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # Dashboards
    path('dashboard/', dashboard, name='dashboard'),
    path('dashboard/admin/', admin_dashboard, name='admin_dashboard'),
    path('dashboard/customer/', customer_dashboard, name='customer_dashboard'),

    # Customers (ADMIN DASHBOARD)
    path('customers/', views.all_customers, name='all_customers'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/view/<int:user_id>/', views.view_customer, name='view_customer'),
    path('customers/edit/<int:user_id>/', views.edit_customer, name='edit_customer'),
    path('customers/delete/<int:user_id>/', views.delete_customer, name='delete_customer'),

    # Accounts
    path('accounts/', views.all_accounts, name='all_accounts'),
    path('create-account/', views.create_account, name='create_account'),
    path('accounts/edit/<int:account_id>/', views.edit_account, name='edit_account'),
    path('accounts/delete/<int:account_id>/', views.delete_account, name='delete_account'),

    # Account actions
    path('account/<int:account_id>/', account_detail, name='account_detail'),
    path('deposit/<int:account_id>/', deposit, name='deposit'),
    path('withdraw/<int:account_id>/', withdraw, name='withdraw'),
    path('transfer/<int:account_id>/', transfer, name='transfer'),

    # Admin features
    path('dashboard/admin/notifications/', views.admin_notifications, name='admin_notifications'),
    path('dashboard/admin/pending-accounts/', views.pending_accounts, name='pending_accounts'),
    path('dashboard/admin/messages/', views.admin_messages, name='admin_messages'),
    path('dashboard/admin/transactions/', views.admin_transactions, name='admin_transactions'),
    path('dashboard/admin/activity-logs/', views.admin_activity_logs, name='admin_activity_logs'),
    path('customers/<int:user_id>/', views.view_customer, name='customer_detail'),

    # Customer features
    path('dashboard/customer/messages/', views.customer_messages, name='customer_messages'),
    path('dashboard/customer/profile/', views.customer_profile, name='customer_profile'),
    path('dashboard/customer/spending-insights/', views.spending_insights, name='spending_insights'),
]