from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home_page'),
    path('student/', views.student_view, name='student_page'),
    path('teacher/login/', views.teacher_login_view, name='teacher_login'),
    path('teacher/signup/', views.teacher_signup_view, name='teacher_signup'),
    path('teacher/dashboard/', views.teacher_dashboard_view, name='teacher_dashboard'),
    path('student/login/', views.student_login_view, name='student_login'),
    path('student/signup/', views.student_signup_view, name='student_signup'),
    path('student/dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('student/logout/', views.student_logout_view, name='student_logout'),
    path('teacher/logout/', views.teacher_logout_view, name='teacher_logout'),
    path('add-subject/', views.add_subject, name='add_subject'),
    path('delete-subject/<int:subject_id>/', views.delete_subject, name='delete_subject'),
    path('rename-subject/<int:subject_id>/', views.rename_subject, name='rename_subject'),
    path('attendance/<str:subject_code>/<str:section>/', views.student_attendance_portal, name='student_attendance_portal'),
    path('student/enroll/', views.student_enroll_subject_view, name='student_enroll'),
    path('teacher/upload-attendance/', views.upload_attendance_photo_view, name='upload_attendance_photo'),
    path('teacher/upload-voice-attendance/', views.upload_voice_attendance_view, name='upload_voice_attendance'),
]