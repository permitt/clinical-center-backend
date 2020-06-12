from rest_framework import permissions
from clinics.models import Appointment
import datetime

class OperatingRoomPermissions(permissions.BasePermission):

    def __init__(self, allowed_methods=['GET', 'POST', 'DELETE', 'PUT']):
        super().__init__()
        self.allowed_methods=allowed_methods

    def has_permission(self, request, view):

        return hasattr(request.user, 'adminAccount')

class AppointmentTypePermissions(permissions.BasePermission):

    def __init__(self, allowed_methods=['GET', 'POST', 'DELETE', 'PUT']):
        super().__init__()
        self.allowed_methods=allowed_methods

    def has_permission(self, request, view):

        return hasattr(request.user, 'adminAccount') or hasattr(request.user,'patient') or hasattr(request.user,'docAccount')

class HealthCardPermissions(permissions.BasePermission):

    def __init__(self, allowed_methods=['GET', 'POST', 'DELETE', 'PUT']):
        super().__init__()
        self.allowed_methods=allowed_methods

    def has_permission(self, request, view):

        if request.method == 'GET':
            if hasattr(request.user, 'patient'):
                return True

            user = request.user.username
            print(user)
            try:
                patient = request.query_params['patient']
            except:
                return False
            now = datetime.datetime.now().date()
            appointments = Appointment.objects.filter(patient=patient)\
                .filter(doctor__email=user)\
                .filter(date__lte=now)\
                .all()

            return len(appointments) > 0

        return False
