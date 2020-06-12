"""clinical_center URL Configuration
"""
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('api/users/', include('users.urls')),
    path('api/clinics/', include('clinics.urls')),
    path('admin/', admin.site.urls),
]

urlpatterns += [url(r'^silk/', include('silk.urls', namespace='silk'))]
