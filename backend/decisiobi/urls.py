"""
URL configuration for decisiobi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Authentication endpoints
    path('api/auth/', include('apps.authentication.urls')),
    path('api/ingestion/', include('apps.ingestion.urls')),
    path('api/nettoyage/', include('apps.nettoyage.urls')),
    path('api/conflits/', include('apps.conflits.urls')),
    path('api/kpi/', include('apps.kpi.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),
    path('api/ia/', include('apps.ia_interpretation.urls')),
    path('api/anomalies/', include('apps.anomalies.urls')),
    path('api/chatbot/', include('apps.chatbot.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
