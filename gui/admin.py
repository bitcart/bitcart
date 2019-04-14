from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _
from . import models


class CustomUserAdmin(UserAdmin):
    model = models.User
    app_label = "authentication"
    list_display = ['username', 'email', 'first_name',
                    'last_name', 'is_staff', 'is_confirmed']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_confirmed',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )


# Register your models here.
admin.site.register(models.User, CustomUserAdmin)
admin.site.register(models.Store)
admin.site.register(models.Product)
admin.site.register(models.Wallet)
