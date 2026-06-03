import os
import csv
import io
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from geopy.distance import geodesic
from django.utils import timezone

from .models import Lecturer, Course, Question, StudentSubmission, AllowedStudent

try:
    import openpyxl
except ImportError:
    openpyxl = None

from docx import Document
from pypdf import PdfReader


# ==========================================================
#             STUDENT VERIFICATION & PORTAL VIEWS
# ==========================================================

def login_portal(request):
    """
    Renders the unified login gatekeeper portal and verifies student authorization
    against the database records before establishing a user context.
    """
    if request.method == "GET" and request.session.get('is_authenticated_student'):
        course_id = request.session.get('authorized_course_id')
        course = get_object_or_404(Course, id=course_id)

        return render(request, 'quiz/login.html', {
            'course': course,
            'student_name': request.session.get('student_name'),
            'index_number': request.session.get('index_number'),
            'is_authenticated': True,
            'lecturers': Lecturer.objects.all()
        })

    if request.method == "POST":
        input_index = request.POST.get('index_number', '').strip().upper()
        course_id = request.POST.get('course_id')

        # 1. Query database to see if this student is explicitly authorized for this exam
        student_check = AllowedStudent.objects.filter(
            index_number=input_index,
            course_id=course_id
        ).first()

        # 2. Strict Verification Gate
        if not student_check:
            messages.error(request, "❌ Access Denied: Your index number is not registered for this examination.")
            return redirect('login_portal')

        # 3. Prevent duplicate exam entry breaches using the authorization model
        if student_check.has_taken_exam:
            messages.error(request, "🚫 Security Alert: You have already submitted this examination.")
            return redirect('login_portal')

        # 4. Success: Secure identity metrics inside session context
        request.session['student_name'] = student_check.full_name
        request.session['index_number'] = student_check.index_number
        request.session['authorized_course_id'] = course_id
        request.session['is_authenticated_student'] = True

        return redirect('login_portal')

    lecturers = Lecturer.objects.all()
    return render(request, 'quiz/login.html', {'lecturers': lecturers})


def get_courses(request):
    lecturer_id = request.GET.get('lecturer_id')
    courses = Course.objects.filter(lecturer_id=lecturer_id).values('id', 'code', 'title')
    return JsonResponse(list(courses), safe=False)


def start_quiz(request):
    """
    Validates physical perimeter parameters and active time brackets before generating the exam sheet.
    """
    student_name = request.session.get('student_name')
    index_number = request.session.get('index_number')
    course_id = request.session.get('authorized_course_id')

    if not student_name or not index_number or not course_id:
        messages.error(request, "Authentication expired or missing context. Please log in again.")
        return redirect('login_portal')

    if request.method == "POST":
        user_lat = request.POST.get('lat')
        user_lng = request.POST.get('lng')

        course = get_object_or_404(Course, id=course_id)

        # 1. Duplicate Entrance Permission Controller
        already_submitted = StudentSubmission.objects.filter(
            index_number=index_number,
            course=course
        ).exists()

        if already_submitted:
            messages.error(request, f"SECURITY LOCKOUT: Index Number {index_number} has an existing paper log.")
            return redirect('login_portal')

        # 2. Secure Datetime Gatekeeper
        current_time = timezone.now()

        if current_time < course.start_time:
            expected_start = course.start_time.strftime("%I:%M %p (%d %b)")
            messages.error(request, f"EXAMINATION NOT YET ACTIVE: Scheduled to begin at {expected_start}.")
            return redirect('login_portal')

        if current_time > course.end_time:
            messages.error(request, "ACCESS DENIED: The examination entry window has closed.")
            return redirect('login_portal')

        # 3. Geolocation Perimeter Verification
        if user_lat and user_lng:
            try:
                student_coords = (float(user_lat), float(user_lng))
                hall_coords = (course.latitude, course.longitude)

                # Geodesic calculation mapping matching your original high-precision framework
                distance = geodesic(student_coords, hall_coords).meters

                if distance > course.radius_meters:
                    messages.error(request,
                                   f"ACCESS DENIED: Physical perimeter verification failed. You are {round(distance)}m away from the authorized zone.")
                    return redirect('login_portal')
            except ValueError:
                messages.error(request, "Invalid hardware location coordinate stream parsing exception.")
                return redirect('login_portal')
        else:
            messages.error(request, "Location tracking verification mandatory. Please enable GPS hardware access.")
            return redirect('login_portal')

        context = {
            'course': course,
            'questions': Question.objects.filter(course=course),
            'student_name': student_name,
            'index_number': index_number,
            'duration_ms': course.duration_minutes * 60 * 1000
        }
        return render(request, 'quiz/exam.html', context)

    return redirect('login_portal')


def submit_quiz(request):
    if request.method == "POST":
        full_name = request.POST.get('full_name', 'Unknown Student').strip()
        index_number = request.POST.get('index_number', '000000').strip().upper()
        course_id = request.POST.get('course_id')
        security_breach = request.POST.get('security_breach', 'false')

        course_obj = get_object_or_404(Course, id=course_id)

        if StudentSubmission.objects.filter(index_number=index_number, course=course_obj).exists():
            return HttpResponse("Form processing rejected: Duplicate paper submission detected for this index profile.",
                                status=403)

        answers = {key: value for key, value in request.POST.items() if key.startswith('q')}
        all_questions = Question.objects.filter(course=course_obj)

        correct_count = 0
        for q in all_questions:
            submitted_val = answers.get(f'q{q.id}')
            if submitted_val:
                if str(submitted_val).strip().upper() == str(q.correct_answer).strip().upper():
                    correct_count += 1

        display_name = full_name
        if security_breach == "true":
            display_name += " [⚠️ TERMINATED FOR TAB SWITCHING]"

        StudentSubmission.objects.create(
            student_name=display_name,
            index_number=index_number,
            course=course_obj,
            submitted_answers=json.dumps(answers),
            score=float(correct_count)
        )

        AllowedStudent.objects.filter(index_number=index_number, course=course_obj).update(has_taken_exam=True)
        request.session.flush()

        return render(request, 'quiz/submitted.html', {
            'student_name': full_name,
            'score': int(correct_count),
            'show_score': False if security_breach == "true" else course_obj.show_scores
        })
    return redirect('login_portal')

    # (Rest of bulk import methods remain unmodified...)

    if request.method == "POST":
        user_lat = request.POST.get('lat')
        user_lng = request.POST.get('lng')

        course = get_object_or_404(Course, id=course_id)

        # === 1. 🛡️ DUPLICATE ENTRANCE PERMISSION CONTROLLER ===
        already_submitted = StudentSubmission.objects.filter(
            index_number=index_number,
            course=course
        ).exists()

        if already_submitted:
            messages.error(request, f"SECURITY LOCKOUT: Index Number {index_number} has an existing paper log.")
            return redirect('login_portal')

        # === 2. SECURE DATETIME GATEKEEPER ===
        current_time = timezone.now()

        if current_time < course.start_time:
            expected_start = course.start_time.strftime("%I:%M %p (%d %b)")
            messages.error(request, f"EXAMINATION NOT YET ACTIVE: Scheduled to begin at {expected_start}.")
            return redirect('login_portal')

        if current_time > course.end_time:
            messages.error(request, "ACCESS DENIED: The examination entry window has closed.")
            return redirect('login_portal')

        # === 3. GEOLOCATION PERIMETER VERIFICATION ===
        if user_lat and user_lng:
            try:
                student_coords = (float(user_lat), float(user_lng))
                hall_coords = (course.latitude, course.longitude)
                distance = geodesic(student_coords, hall_coords).meters

                if distance > course.radius_meters:
                    messages.error(request,
                                   f"ACCESS DENIED: You are {round(distance)}m away from the authorized perimeter zone.")
                    return redirect('login_portal')
            except ValueError:
                messages.error(request, "Invalid hardware location coordinate stream parsing exception.")
                return redirect('login_portal')
        else:
            messages.error(request, "Location tracking verification mandatory. Please enable GPS access.")
            return redirect('login_portal')

        # Everything matches securely: Deliver exam blueprint container layout
        context = {
            'course': course,
            'questions': Question.objects.filter(course=course),
            'student_name': student_name,
            'index_number': index_number,
            'duration_ms': course.duration_minutes * 60 * 1000
        }
        return render(request, 'quiz/exam.html', context)

    return redirect('login_portal')


def submit_quiz(request):
    if request.method == "POST":
        full_name = request.POST.get('full_name', 'Unknown Student').strip()
        index_number = request.POST.get('index_number', '000000').strip().upper()
        course_id = request.POST.get('course_id')
        security_breach = request.POST.get('security_breach', 'false')

        course_obj = get_object_or_404(Course, id=course_id)

        # Double check submission existence directly at the database submission pipeline
        if StudentSubmission.objects.filter(index_number=index_number, course=course_obj).exists():
            return HttpResponse("Form processing rejected: Duplicate paper submission detected for this index profile.",
                                status=403)

        answers = {key: value for key, value in request.POST.items() if key.startswith('q')}
        all_questions = Question.objects.filter(course=course_obj)

        correct_count = 0
        for q in all_questions:
            submitted_val = answers.get(f'q{q.id}')
            if submitted_val:
                if str(submitted_val).strip().upper() == str(q.correct_answer).strip().upper():
                    correct_count += 1

        display_name = full_name
        if security_breach == "true":
            display_name += " [⚠️ TERMINATED FOR TAB SWITCHING]"

        # Save student submission logs securely
        StudentSubmission.objects.create(
            student_name=display_name,
            index_number=index_number,
            course=course_obj,
            submitted_answers=json.dumps(answers),
            score=float(correct_count)
        )

        # Toggle structural lookup record flag to lock student out of subsequent portal attempts
        AllowedStudent.objects.filter(index_number=index_number, course=course_obj).update(has_taken_exam=True)

        # Clean out temporary workspace registration details from active device sessions
        request.session.flush()

        return render(request, 'quiz/submitted.html', {
            'student_name': full_name,
            'score': int(correct_count),
            'show_score': False if security_breach == "true" else course_obj.show_scores
        })
    return redirect('login_portal')


# ==========================================================
#             ADVANCED BULK QUESTIONS IMPORT ENGINE
# ==========================================================

def import_questions_page(request):
    """Renders the HTML upload interface page for lecturers."""
    if not request.user.is_staff:
        return redirect('login_portal')

    context = {
        'courses': Course.objects.all()
    }
    return render(request, 'admin/import_questions.html', context)


def import_questions_all_formats(request):
    """Processes document streams, routing parsing logic automatically based on extensions."""
    if request.method != "POST" or not request.FILES.get('uploaded_document'):
        return redirect('login_portal')

    course_id = request.POST.get('course_id')
    course_obj = get_object_or_404(Course, id=course_id)
    uploaded_file = request.FILES['uploaded_document']

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    QTYPE_MAP = {
        'MCQ': 'MCQ', 'MULTIPLE CHOICE': 'MCQ', 'MULTIPLE_CHOICE': 'MCQ',
        'FITB': 'FITB', 'FILL IN THE BLANK': 'FITB', 'FILL_IN_THE_BLANK': 'FITB',
        'THEORY': 'THEORY', 'WRITTEN ESSAY': 'THEORY', 'ESSAY': 'THEORY'
    }

    try:
        # === 1. DIRECT MICROSOFT EXCEL PARSER (.xlsx) ===
        if ext == '.xlsx':
            if not openpyxl:
                return HttpResponse("Server lacks Excel processor installation (openpyxl).", status=500)
            wb = openpyxl.load_workbook(uploaded_file, data_only=True)
            sheet = wb.active

            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row and len(row) >= 7 and row[0]:
                    raw_type = str(row[1]).strip().upper()
                    clean_type = QTYPE_MAP.get(raw_type, 'MCQ')

                    Question.objects.create(
                        course=course_obj,
                        text=str(row[0]).strip(),
                        q_type=clean_type,
                        option_a=str(row[2]).strip() if row[2] else "",
                        option_b=str(row[3]).strip() if row[3] else "",
                        option_c=str(row[4]).strip() if row[4] else "",
                        option_d=str(row[5]).strip() if row[5] else "",
                        correct_answer=str(row[6]).strip()
                    )

        # === 2. MICROSOFT WORD GRID PARSER (.docx) ===
        elif ext == '.docx':
            doc = Document(uploaded_file)
            if doc.tables:
                table = doc.tables[0]
                for i, row in enumerate(table.rows):
                    if i == 0:
                        continue  # Skip headers

                    cells = [cell.text.strip() for cell in row.cells]
                    if len(cells) >= 7 and cells[0]:
                        raw_type = cells[1].strip().upper()
                        clean_type = QTYPE_MAP.get(raw_type, 'MCQ')

                        Question.objects.create(
                            course=course_obj,
                            text=cells[0], q_type=clean_type,
                            option_a=cells[2], option_b=cells[3], option_c=cells[4], option_d=cells[5],
                            correct_answer=cells[6]
                        )
            else:
                return HttpResponse("Word document parsing error: Could not find structured table grid layout.",
                                    status=400)

        # === 3. PORTABLE DOCUMENT FORMAT SCANNER (.pdf) ===
        elif ext == '.pdf':
            reader = PdfReader(uploaded_file)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"

            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            for line in lines:
                parts = line.split(',')
                if len(parts) >= 7 and not parts[0].lower().startswith('text'):
                    raw_type = parts[1].strip().upper()
                    clean_type = QTYPE_MAP.get(raw_type, 'MCQ')

                    Question.objects.create(
                        course=course_obj,
                        text=parts[0].strip(), q_type=clean_type,
                        option_a=parts[2].strip(), option_b=parts[3].strip(),
                        option_c=parts[4].strip(), option_d=parts[5].strip(),
                        correct_answer=parts[6].strip()
                    )

        # === 4. NATIVE ENCODING COMPLIANT CSV PARSER (.csv) ===
        elif ext == '.csv':
            try:
                decoded_file = uploaded_file.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                decoded_file = uploaded_file.read().decode('latin-1')

            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string)
            next(reader)  # Skip headers

            for row in reader:
                if len(row) >= 7 and row[0]:
                    raw_type = row[1].strip().upper()
                    clean_type = QTYPE_MAP.get(raw_type, 'MCQ')

                    Question.objects.create(
                        course=course_obj,
                        text=row[0].strip(), q_type=clean_type,
                        option_a=row[2].strip(), option_b=row[3].strip(),
                        option_c=row[4].strip(), option_d=row[5].strip(),
                        correct_answer=row[6].strip()
                    )
        else:
            return HttpResponse("Unsupported file format exception.", status=400)

        return redirect('/admin/quiz/question/')

    except Exception as e:
        return HttpResponse(f"System parsing exception caught during data synchronization: {str(e)}", status=500)


# ==========================================================
#             BLUEPRINT TEMPLATE DOWNLOAD ENDPOINTS
# ==========================================================

def download_excel_template(request):
    if not request.user.is_staff:
        return redirect('login_portal')
    if not openpyxl:
        return HttpResponse("Excel layout components missing on environment runtime.", status=500)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Question Import Template"

    headers = ['text', 'q_type', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']
    ws.append(headers)

    sample_row = [
        "Example Question: What language is Django written in?",
        "Multiple Choice", "Java", "Python", "C++", "PHP", "B"
    ]
    ws.append(sample_row)

    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="question_import_blueprint.xlsx"'
    wb.save(response)
    return response


def download_word_template(request):
    if not request.user.is_staff:
        return redirect('login_portal')

    doc = Document()
    doc.add_heading('Question Import Blueprint Grid', level=1)
    doc.add_paragraph('Fill your data inside the structured table layout below. Do not delete the top headers row.')

    table = doc.add_table(rows=2, cols=7)
    table.style = 'Table Grid'

    headers = ['text', 'q_type', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']
    for idx, name in enumerate(headers):
        table.cell(0, idx).text = name
        table.cell(0, idx).paragraphs[0].runs[0].font.bold = True

    sample_values = ["Sample Target?", "Multiple Choice", "Opt A", "Opt B", "Opt C", "Opt D", "A"]
    for idx, value in enumerate(sample_values):
        table.cell(1, idx).text = value

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = 'attachment; filename="question_import_blueprint.docx"'
    doc.save(response)
    return response


# ==========================================================
#         🔥 NEW: ALLOWED STUDENTS BULK ROSTER UPLOADER
# ==========================================================

@staff_member_required
def upload_allowed_students(request):
    """Processes incoming class rosters (.xlsx / .csv) and registers students into an exam."""
    if request.method == "POST":
        course_id = request.POST.get("course_id")
        file_ref = request.FILES.get("student_file")

        if not course_id or not file_ref:
            messages.error(request, "Please select a valid course and attach a roster file.")
            return redirect("admin:quiz_allowedstudent_changelist")

        try:
            course = Course.objects.get(id=course_id)
            filename = file_ref.name.lower()
            students_to_create = []
            duplicate_count = 0
            success_count = 0

            # --- A. PROCESS EXCEL (.XLSX) ROSTERS ---
            if filename.endswith(".xlsx"):
                if not openpyxl:
                    messages.error(request, "Server lacks Excel processor installation (openpyxl).")
                    return redirect("admin:quiz_allowedstudent_changelist")

                wb = openpyxl.load_workbook(file_ref, data_only=True)
                sheet = wb.active

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if not row or not row[0]:
                        continue
                    idx = str(row[0]).strip().upper()
                    name = str(row[1]).strip() if len(row) > 1 and row[1] else "Unknown Student"

                    if AllowedStudent.objects.filter(index_number=idx, course=course).exists():
                        duplicate_count += 1
                        continue

                    students_to_create.append(AllowedStudent(course=course, index_number=idx, full_name=name))

            # --- B. PROCESS STANDARD CSV (.CSV) ROSTERS ---
            elif filename.endswith(".csv"):
                try:
                    decoded_file = file_ref.read().decode('utf-8-sig').splitlines()
                except UnicodeDecodeError:
                    file_ref.seek(0)
                    decoded_file = file_ref.read().decode('latin-1').splitlines()

                reader = csv.reader(decoded_file)
                next(reader, None)  # Skip table header row

                for row in reader:
                    if not row or not row[0]:
                        continue
                    idx = str(row[0]).strip().upper()
                    name = str(row[1]).strip() if len(row) > 1 and row[1] else "Unknown Student"

                    if AllowedStudent.objects.filter(index_number=idx, course=course).exists():
                        duplicate_count += 1
                        continue

                    students_to_create.append(AllowedStudent(course=course, index_number=idx, full_name=name))
            else:
                messages.error(request, "Unsupported file format. Please upload an .xlsx or .csv roster.")
                return redirect("admin:quiz_allowedstudent_changelist")

            # High-speed relational bulk insertion
            if students_to_create:
                AllowedStudent.objects.bulk_create(students_to_create)
                success_count = len(students_to_create)

            messages.success(
                request,
                f"Roster uploaded successfully! Registered: {success_count} students. Skipped: {duplicate_count} existing duplicate entries."
            )

        except Course.DoesNotExist:
            messages.error(request, "Selected course verification mapping failed.")
        except Exception as e:
            messages.error(request, f"Error processing file layout: {str(e)}")

    return redirect("admin:quiz_allowedstudent_changelist")