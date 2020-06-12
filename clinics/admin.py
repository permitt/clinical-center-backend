from django.contrib import admin
from . import models

# Register your models here.
admin.site.register(models.PriceList)
admin.site.register(models.Clinic)
admin.site.register(models.Appointment)
admin.site.register(models.AppointmentType)
admin.site.register(models.OperatingRoom)
admin.site.register(models.ClinicRating)
admin.site.register(models.DoctorRating)
admin.site.register(models.Specialization)
admin.site.register(models.Holiday)
admin.site.register(models.HealthCard)
admin.site.register(models.Operation)