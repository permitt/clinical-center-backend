from django.urls import path
from rest_framework import routers
from . import views

router = routers.SimpleRouter()
router.register('appointment', views.AppointmentViewSet, basename="appointment")
router.register('operatingroom', views.OperatingRoomView, basename="operatingroom")
router.register('appointment-type', views.AppointmentTypeView, basename="appointment-type")
router.register('holiday', views.HolidayRequestView, basename="holiday")
router.register('health-card', views.HealthCardView, basename="health-card")
router.register('operation', views.OperationView, basename="operation")
router.register('clinic', views.ClinicListView)
router.register('doctor-rating', views.DoctorRatingView, basename='doctor-rating')
router.register('clinic-rating', views.ClinicRatingView, basename='clinic-rating')

urlpatterns = [
        path('appointment/check/', views.appointmentCheck),
        path('holiday/resolve/<int:pk>/', views.resolveRequest),
        path('appointment/schedule', views.scheduleAppointment),
        path('clinicreports/', views.reports),
        path('income/', views.income),
        path('adminclinic/', views.adminClinic),
        path('appointment/appterm/', views.appTerm),
        *router.urls
    ]