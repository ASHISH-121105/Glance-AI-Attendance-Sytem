from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout  
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from users.models import TeacherProfile, StudentProfile, Subject, AttendanceSession, AttendanceRecord
import base64
import numpy as np
import json
from django.core.files.base import ContentFile
from .face_pipeline import FacePipeline
from .voice_pipeline import VoicePipeline
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from itertools import groupby
from django.shortcuts import get_object_or_404
from pydub import AudioSegment
import os
from django.db import transaction



#============================================
# ffmpeg (AUDIO FILE HANDLING)
#============================================
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
AudioSegment.converter = os.path.join(os.getcwd(), "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(os.getcwd(), "ffprobe.exe")


def home_view(request):
    return render(request, 'home.html')

def student_view(request):
    return render(request, 'student.html')


#--------------------------------------------
#        TEACHER WORKFLOW NODES
#--------------------------------------------
def teacher_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('auth_username', '').strip()
        password = request.POST.get('auth_password', '')

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if hasattr(user, 'teacher_profile'):
                login(request, user)
                messages.success(request, "Welcome back to the Control Suite Panel.")
                return redirect('teacher_dashboard')
            else:
                messages.error(request, "Access Denied: This checkpoint is strictly for teachers.")
        else:
            messages.error(request, "Invalid username or password credentials.")
            return render(request, 'teacher_login.html')

    return render(request, 'teacher_login.html')


def teacher_signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        full_name = request.POST.get('name', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if password != confirm_password:
            messages.error(request, "Passwords do not match verification standards.")
            return render(request, 'teacher_signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "This username is already initialized in systemic records.")
            return render(request, 'teacher_signup.html')

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password)
            TeacherProfile.objects.create(user=user, full_name=full_name)

        messages.success(request, "Administrative credentials registered successfully! Please log in.")
        return redirect('teacher_login')

    return render(request, 'teacher_signup.html')


def teacher_logout_view(request):
    logout(request)
    return redirect('teacher_login')


@login_required
def teacher_dashboard_view(request):
    # 1. Initialize an empty dictionary so the template doesn't crash if the user isn't a teacher
    grouped_subjects = {}
    
    # 2. Check if the logged-in user has a valid teacher profile relation
    if hasattr(request.user, 'teacher_profile'):
        profile = request.user.teacher_profile
        
        # 3. Use the 'profile' variable directly to avoid underscore naming mismatches
        subjects = Subject.objects.filter(teacher=profile)
        
        # 4. Correctly indent the loop inside the function to group subjects by class name
        for subject in subjects:
            if subject.class_name not in grouped_subjects:
                grouped_subjects[subject.class_name] = []
            grouped_subjects[subject.class_name].append(subject)
            
    else:
        # Fallback handling: If a non-teacher tries to access this page, safely redirect them
        return redirect('') 
    # 5. Pack the safely evaluated dictionary data into the template context layer
    context = {
        'grouped_subjects': grouped_subjects,
    }
    return render(request, 'teacher_dashboard.html', context)


@csrf_exempt
@login_required
def add_subject(request):
    if request.method == 'POST':
        try:
            profile = request.user.teacher_profile 
            new_subject = Subject.objects.create(
                teacher=profile, 
                name=request.POST.get('name'),
                code=request.POST.get('code'),
                class_name=request.POST.get('class_name'),
                section=request.POST.get('section')
            )
            return JsonResponse({'status': 'success', 'id': new_subject.id})
        except Exception as e:
            print(f"Error saving subject: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)


@csrf_exempt
@login_required
def delete_subject(request, subject_id):
    if request.method == 'POST':
        try:
            profile = request.user.teacher_profile
            subject = get_object_or_404(Subject, id=subject_id, teacher=profile)
            subject.delete()
            return JsonResponse({'status': 'success'})
        except AttributeError:
            return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=400)
    return JsonResponse({'status': 'error'}, status=400)


@csrf_exempt
@login_required
def rename_subject(request, subject_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        profile = request.user.teacher_profile
        subject = get_object_or_404(Subject, id=subject_id, teacher=profile)
        
        subject.name = data.get('name')
        subject.code = data.get('code')
        subject.class_name = data.get('class_name')
        subject.section = data.get('section')
        subject.save()
        
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


#--------------------------------------------
#        STUDENT WORKFLOW NODES
#--------------------------------------------
def student_signup_view(request):
    if request.method == 'POST':
        roll_number = request.POST.get('roll_number', '').strip()
        name = request.POST.get('name', '').strip()
        university_name = request.POST.get('university_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Capture raw biometric payload nodes
        face_base64 = request.POST.get('face_image_base64', '')
        voice_base64 = request.POST.get('voice_base64', '')

        # Defensive Guardrail: Ensure at least one modality is submitted
        if not face_base64 and not voice_base64: 
            messages.error(request, "Biometric registration entry missing. Please provide Face or Voice data.")
            return render(request, 'student_signup.html')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'student_signup.html')

        if User.objects.filter(username=roll_number).exists():
            messages.error(request, "This Roll Number node is already active.")
            return render(request, 'student_signup.html')

        # Initialize registration profile matrices
        primary_face_vector = None
        primary_voice_vector = None
        is_face_reg = False
        is_voice_reg = False

        # --- OPTION A: PROCESS FACE BIOMETRICS ---
        if face_base64:
            try:
                face_format, face_imgstr = face_base64.split(';base64,')
                face_ext = face_format.split('/')[-1]
                face_file = ContentFile(base64.b64decode(face_imgstr), name=f"face_{roll_number}.{face_ext}")
                
                face_vector = FacePipeline().extract_multiple_embeddings(face_file)
                if not face_vector:
                    messages.error(request, "Face detection matrix analysis failed. Ensure proper framing.")
                    return render(request, 'student_signup.html')
                
                primary_face_vector = face_vector[0]['embedding']
                is_face_reg = True
            except Exception as e:
                print(f"❌ Face Pipeline Error: {e}")
                messages.error(request, "Face verification matrix corrupt. Re-take snapshot.")
                return render(request, 'student_signup.html')

        # --- OPTION B: PROCESS VOICE BIOMETRICS ---
        if voice_base64:
            try:
                # The VoicePipeline extracts vector matrices and strips out background floor noise
                voice_vector = VoicePipeline().extract_voice_embedding(voice_base64)
                if not voice_vector:
                    messages.error(request, "Vocal node token extraction failed. Speak clearly without ambient static noise.")
                    return render(request, 'student_signup.html')
                
                primary_voice_vector = voice_vector
                is_voice_reg = True
            except Exception as e:
                print(f"❌ Voice Pipeline Error: {e}")
                messages.error(request, "Voice token encoding exception occurred. Please try recording again.")
                return render(request, 'student_signup.html')

        # --- DATABASE PROFILE COMPILATION ---
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=roll_number, email=email, password=password)
                
                StudentProfile.objects.create(
                    user=user,
                    full_name=name,
                    roll_number=roll_number,
                    university_name=university_name,
                    face_encoding=json.dumps(primary_face_vector) if primary_face_vector else None,
                    voice_encoding=json.dumps(primary_voice_vector) if primary_voice_vector else None,
                    is_face_registered=is_face_reg,
                    is_voice_registered=is_voice_reg,
                )
            messages.success(request, "Biometrics registered successfully! Proceed to portal entry access.")
            return redirect('student_login')
            
        except Exception as e:
            print(f"❌ Database Transaction Failed: {e}")
            messages.error(request, "An internal error occurred while compiling your profile layout. Please try again.")
            return render(request, 'student_signup.html')

    return render(request, 'student_signup.html')


def student_login_view(request):
    if request.method == 'POST':
        roll_number = request.POST.get('roll_number', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=roll_number, password=password)
        
        if user is not None:
            if hasattr(user, 'student_profile'):
                login(request, user)
                messages.success(request, f"Welcome back, {user.student_profile.full_name}.")
                return redirect('student_dashboard')
            else:
                messages.error(request, "Access Denied: This checkpoint is strictly for student portals.")
        else:
            messages.error(request, "Invalid Roll Number or Password credentials.")

    return render(request, 'student_login.html')


@login_required
def student_dashboard_view(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('teacher_dashboard')
        
    student_profile = request.user.student_profile
    # Fetch all subjects where the current student is registered
    enrolled_classes = Subject.objects.filter(students=student_profile)
    
    selected_subject_id = request.GET.get('subject_id')
    selected_subject = None
    attendance_stats = None
    records_history = []
    
    if selected_subject_id:
        selected_subject = get_object_or_404(Subject, id=selected_subject_id, students=student_profile)
        
        # Pull all chronological records for this student and subject
        records_history = AttendanceRecord.objects.filter(
            session__subject=selected_subject,
            student=student_profile
        ).select_related('session').order_by('-session__created_at')
        
        # Calculate quantitative aggregates
        total_sessions = records_history.count()
        present_sessions = records_history.filter(status='Present').count()
        absent_sessions = total_sessions - present_sessions
        
        percentage = 0.0
        if total_sessions > 0:
            percentage = round((present_sessions / total_sessions) * 100, 1)
            
        attendance_stats = {
            'total': total_sessions,
            'present': present_sessions,
            'absent': absent_sessions,
            'percentage': percentage
        }

    context = {
        'enrolled_classes': enrolled_classes,
        'selected_subject': selected_subject,
        'attendance_stats': attendance_stats,
        'records_history': records_history,
    }
    return render(request, 'student_dashboard.html', context)


@login_required
def student_attendance_portal(request, subject_code, section):
    if not hasattr(request.user, 'student_profile'):
        return redirect('student_login')
        
    student_profile = request.user.student_profile
    current_subject = get_object_or_404(Subject, code=subject_code, section=section)
    
    # ──> REMOVED FALLBACK: Keeps the sidebar accurate to you while viewing a class
    my_enrolled_subjects = student_profile.enrolled_subjects.all()
    
    context = {
        'subject': current_subject,
        'subjects': my_enrolled_subjects,
        'student': student_profile
    }
    return render(request, 'student_dashboard.html', context)

@csrf_exempt
@login_required
def student_enroll_subject_view(request):
    if request.method == 'POST' and request.user.is_authenticated:
        # Secure the profile guard check immediately
        if not hasattr(request.user, 'student_profile'):
            messages.error(request, "Access Denied: Account lacks a Student Profile.")
            return redirect('student_login')

        subject_code = request.POST.get('subject_code', '').strip()
        section = request.POST.get('section', '').strip()
        
        # Using __iexact ensures case-insensitive matching for robust inputs
        subject_node = Subject.objects.filter(
            code__iexact=subject_code, 
            section__iexact=section
        ).first()
        
        if subject_node:
            student_profile = request.user.student_profile
            
            # ──> FIXED: This joins the student profile to the many-to-many relationship table!
            subject_node.students.add(student_profile)
            
            messages.success(request, f"Successfully enrolled in {subject_node.name} ({subject_node.section})!")
        else:
            messages.error(request, f"Could not find an active subject matching code '{subject_code}' and section '{section}'.")
            
    return redirect('student_dashboard')


def student_logout_view(request):
    logout(request)
    messages.success(request, "Logged out securely. Session tracking terminated.")
    return redirect('student_login')

# ──> FIXED: Removed completely redundant and defective create_subject_view function


# ================================================
#   TAKE ATTENDANCE
# ================================================
@csrf_exempt
@login_required
def upload_attendance_photo_view(request):
    if request.method == 'POST' and request.FILES.get('class_photo'):
        try:
            subject_id = request.POST.get('subject_id')
            class_photo = request.FILES['class_photo']
            
            # 1. Fetch Subject and its enrolled student list
            teacher_profile = request.user.teacher_profile
            subject_node = get_object_or_404(Subject, id=subject_id, teacher=teacher_profile)
            enrolled_students = subject_node.students.all() # Many-to-Many query
            
            if not enrolled_students.exists():
                return JsonResponse({'status': 'error', 'message': 'No students are currently enrolled in this subject matrix.'}, status=400)
            
            # 2. Extract multiple facial vector sets from the uploaded class photo
            pipeline = FacePipeline()
            detected_faces = pipeline.extract_multiple_embeddings(class_photo)
            
            if not detected_faces:
                return JsonResponse({'status': 'error', 'message': 'No faces detected in the uploaded frame. Check lightning or contrast parameters.'}, status=400)
            
            # 3. Open an active database entry tracking node
            with transaction.atomic():
                current_session = AttendanceSession.objects.create(subject=subject_node, is_active=False)
                
                marked_present_count = 0
                present_student_names = []
                
                # Pre-initialize everyone as Absent for security redundancy
                for student in enrolled_students:
                    AttendanceRecord.objects.create(session=current_session, student=student, status='Absent')
                
                # 4. Core AI Matching Iteration Engine
                for face in detected_faces:
                    uploaded_embedding = np.array(face['embedding'])
                    
                    best_match_student = None
                    lowest_distance = 1.0  # Threshold baseline setting (1.0 is max range variance)
                    
                    for student in enrolled_students:
                        if not student.face_encoding:
                            continue
                            
                        registered_embedding = np.array(json.loads(student.face_encoding))
                        
                        # Mathematical formulation: Calculating Euclidean vector spatial variance
                        distance = np.linalg.norm(uploaded_embedding - registered_embedding)
                        
                        # Track the absolute closest profile match
                        if distance < lowest_distance:
                            lowest_distance = distance
                            best_match_student = student
                    
                    # 5. Accuracy Gate Validation (0.55 threshold value protects against false duplicates)
                    if lowest_distance <= 0.55 and best_match_student is not None:
                        record = AttendanceRecord.objects.filter(session=current_session, student=best_match_student).first()
                        if record and record.status != 'Present':
                            record.status = 'Present'
                            record.save()
                            marked_present_count += 1
                            present_student_names.append(best_match_student.full_name)
            
            return JsonResponse({
                'status': 'success',
                'session_id': current_session.id,
                'detected': len(detected_faces),
                'marked_present': marked_present_count,
                'present_list': present_student_names,
                'message': f"Processed {len(detected_faces)} structural vectors. Verified {marked_present_count} students successfully!"
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid file processing channel deployment request.'}, status=400)


@csrf_exempt
@login_required
def upload_voice_attendance_view(request):
    """
    Processes real-time audio clips captured live by the teacher's microphone.
    Extracts high-dimensional acoustic embeddings and matches them against enrolled student patterns.
    """
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        audio_file = request.FILES.get('voice_sample') # Intercepts the raw .webm audio stream data chunk
        
        if not subject_id or not audio_file:
            return JsonResponse({'status': 'error', 'message': 'Missing data context streams: Subject ID or voice sample input data is absent.'}, status=400)
            
        try:
            # 1. Fetch Subject and verify teacher relationship parameters
            teacher_profile = request.user.teacher_profile
            subject_node = get_object_or_404(Subject, id=subject_id, teacher=teacher_profile)
            enrolled_students = subject_node.students.all()
            
            if not enrolled_students.exists():
                return JsonResponse({'status': 'error', 'message': 'No students are currently enrolled in this subject matrix.'}, status=400)
            
            # 2. Transcode binary audio file payload into a spatial Base64 string context
            audio_bytes = audio_file.read()
            voice_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # 3. Extract 256-dimensional vocal token vector embedding array
            pipeline = VoicePipeline()
            uploaded_embedding = pipeline.extract_voice_embedding(voice_base64)
            
            if not uploaded_embedding:
                return JsonResponse({'status': 'error', 'message': 'Vocal node token extraction failed. Ensure clear speaker input with low background floor noise.'}, status=400)
                
            uploaded_embedding_np = np.array(uploaded_embedding)
            
            # 4. Iterate and isolate the matching profile template using Euclidean distance formula calculations
            best_match_student = None
            lowest_distance = 1.0  # Baseline distance value threshold bounds
            
            for student in enrolled_students:
                if not student.voice_encoding:
                    continue
                
                # Deserialize the vector array list from text storage fields
                registered_embedding = np.array(json.loads(student.voice_encoding))
                
                # Compute Euclidean structural spatial variance distance metric
                distance = np.linalg.norm(uploaded_embedding_np - registered_embedding)
                
                if distance < lowest_distance:
                    lowest_distance = distance
                    best_match_student = student
            
            # 5. Core Gate Validation (0.65 threshold filter safeguards voice biometric accuracy inputs)
            if lowest_distance <= 0.65 and best_match_student is not None:
                with transaction.atomic():
                    # Instantiates a fresh attendance logging timeline track node
                    current_session = AttendanceSession.objects.create(subject=subject_node, is_active=False)
                    
                    # Pre-populate all student rows as Absent for tracking security integrity
                    for s in enrolled_students:
                        AttendanceRecord.objects.create(session=current_session, student=s, status='Absent')
                    
                    # Update status to Present for the matched identity token profile
                    record = AttendanceRecord.objects.filter(session=current_session, student=best_match_student).first()
                    if record:
                        record.status = 'Present'
                        record.save()
                
                return JsonResponse({
                    'status': 'success',
                    'student_name': best_match_student.full_name,
                    'message': f"Biometric voice pattern successfully verified for student user profile node: {best_match_student.full_name}."
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Speaker pattern validation checkpoint failed. Voice parameters do not match enrollment templates.'}, status=400)
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Internal engine failure: {str(e)}'}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid view endpoint deployment access request method type.'}, status=400)