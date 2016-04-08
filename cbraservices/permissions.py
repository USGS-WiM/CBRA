from rest_framework import permissions
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist


class IsStaff(permissions.BasePermission):
    """
    Custom permission to only allow staff users access to objects.
    """

    def has_permission(self, request, view):
        try:
            # returns True if user is staff, False if user is not staff
            return User.objects.get(username=request.user).is_staff
        except ObjectDoesNotExist:
            # always return False if the user does not exist
            return False