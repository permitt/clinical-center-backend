from django.contrib import admin

from clinics.models import DiagnosisReport
from . import models

# Register your models here.
admin.site.register(models.Patient)
admin.site.register(models.ClinicAdmin)
admin.site.register(models.Doctor)
admin.site.register(models.Schedule)
admin.site.register(models.Nurse)
admin.site.register(DiagnosisReport)
