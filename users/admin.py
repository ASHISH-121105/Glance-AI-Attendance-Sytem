from django.contrib import admin
from .models import TeacherProfile, StudentProfile
from .models import Subject

class SubjectEnrollmentInline(admin.TabularInline):
    model = Subject.students.through  # References the hidden join table Django built
    extra = 1                         # Shows 1 empty row by default to quickly add a class
    verbose_name = "Course Enrollment Node"
    verbose_name_plural = "Course Enrollment Nodes"

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('id','full_name', 'get_username', 'created_at')
    search_fields = ('full_name', 'user__username')

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'get_username', 'created_at')
    search_fields = ('full_name', 'user__username')

    inlines = [SubjectEnrollmentInline]

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'

    def display_enrolled_subjects(self, obj):
        return ", ".join([f"{sub.name} ({sub.section})" for sub in obj.enrolled_subjects.all()])
    display_enrolled_subjects.short_description = 'Enrolled Subjects'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'class_name', 'section')
    list_filter = ('class_name',) 
    ordering = ('class_name', 'name')
    filter_horizontal = ('students',)