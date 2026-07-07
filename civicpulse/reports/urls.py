from django.urls import path
from . import views

urlpatterns = [
    path('reports/', views.reports),
    path('reports/<int:pk>/status/', views.update_status),
    path('reports/<int:pk>/export/', views.export_pdf),
    path('dashboard/', views.dashboard),
]