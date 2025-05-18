from django.urls import path
from .views import (
    RegisterView, LoginView, SkillListCreateView, SkillUpdateDeleteView, ResumeUploadView,CheckUsernameView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('skills/', SkillListCreateView.as_view(), name='skill-list-create'),
    path('skills/<int:pk>/', SkillUpdateDeleteView.as_view(), name='skill-update-delete'),
    path('upload-resume/', ResumeUploadView.as_view(), name='upload-resume'),
    path('check-username', CheckUsernameView.as_view(), name='check-username'),
]
