from django.db import models
from django.contrib.auth.models import User

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    full_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Teacher: {self.full_name} (@{self.user.username})"

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    full_name = models.CharField(max_length=150)
    roll_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    university_name = models.CharField(max_length=255, null=True, blank=True)
    face_encoding = models.TextField(null=True, blank=True) # Stores the 128-d vector array as a string string
    voice_encoding = models.TextField(null=True, blank=True)
    is_face_registered = models.BooleanField(default=False)
    is_voice_registered = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Student: {self.full_name} | Roll: {self.roll_number}"
    
class Subject(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    class_name = models.CharField(max_length=50)
    section = models.CharField(max_length=20)
    students = models.ManyToManyField(StudentProfile, blank=True, related_name='enrolled_subjects')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"
    
class AttendanceSession(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendance_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session for {self.subject.name} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
    )
    
    # Links a specific student to a specific tracking session
    session = models.ForeignKey('AttendanceSession', on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey('StudentProfile', on_delete=models.CASCADE, related_name='attendance_history')
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Absent')

    class Meta:
        unique_together = ('session', 'student')  # Prevents duplicate entries for the same student in a single session

    def __str__(self):
        return f"{self.student.full_name} - {self.session.subject.name}: {self.status}"