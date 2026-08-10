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
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
import os

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

# Serve frontend SPA in production
SPA_DIR = settings.BASE_DIR.parent / 'decision-spark' / 'dist' / 'client'
if SPA_DIR.exists():
    from django.views.static import serve as static_serve

    def serve_spa(request, path=''):
        index = SPA_DIR / 'index.html'
        if index.exists():
            return static_serve(request, str(path or 'index.html'), document_root=str(SPA_DIR))
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound('Frontend not built')

    urlpatterns += [
        re_path(r'^(?:assets/.*)$', lambda req, path='': static_serve(req, path, document_root=str(SPA_DIR / 'assets'))),
        re_path(r'^(?!api/|admin/|media/|static/).*$', serve_spa),
    ]
