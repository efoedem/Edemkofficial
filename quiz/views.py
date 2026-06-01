import os
import csv
import io
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from geopy.distance import geodesic
from .models import Lecturer, Course, Question, StudentSubmission
from django.utils import timezone

# Binary document file parsers
import openpyxl
from docx import Document
from pypdf import PdfReader


def login_page(request):
    lecturers = Lecturer.objects.all()
    return render(request, 'quiz/login.html', {'lecturers': lecturers})


def get_courses(request):
    lecturer_id = request.GET.get('lecturer_id')
    courses = Course.objects.filter(lecturer_id=lecturer_id).values('id', 'code', 'title')
    return JsonResponse(list(courses), safe=False)


def start_quiz(request):
    if request.method == "POST":
        course_id = request.POST.get('course_id')
        full_name = request.POST.get('full_name', '').strip()

        # Standardize the incoming index number to uppercase format
        index_number = request.POST.get('index_number', '').strip().upper()

        user_lat = request.POST.get('lat')
        user_lng = request.POST.get('lng')

        # Basic identity validation gatekeeper
        if not course_id or not index_number or not full_name:
            return render(request, 'quiz/login.html', {
                'lecturers': Lecturer.objects.all(),
                'error': "ACCESS DENIED: All verification fields (Full Name, Index Number, and Course) must be filled."
            })

        course = get_object_or_404(Course, id=course_id)

        # === 1. 🛡️ DUPLICATE ENTRANCE PERMISSION CONTROLLER ===
        # Blocks students from starting the exact same examination session twice
        already_submitted = StudentSubmission.objects.filter(
            index_number=index_number,
            course=course
        ).exists()

        if already_submitted:
            return render(request, 'quiz/login.html', {
                'lecturers': Lecturer.objects.all(),
                'error': f"SECURITY LOCKOUT: Index Number {index_number} has already started or completed this examination session."
            })

        # === 2. SECURE DATETIME GATEKEEPER ===
        current_time = timezone.now()

        if current_time < course.start_time:
            expected_start = course.start_time.strftime("%I:%M %p (%d %b)")
            return render(request, 'quiz/login.html', {
                'lecturers': Lecturer.objects.all(),
                'error': f"EXAMINATION NOT YET ACTIVE: This session is scheduled to begin at {expected_start}."
            })

        if current_time > course.end_time:
            return render(request, 'quiz/login.html', {
                'lecturers': Lecturer.objects.all(),
                'error': "ACCESS DENIED: The examination entry portal window closed for this course session."
            })

        # === 3. GEOLOCATION PERIMETER VERIFICATION ===
        if user_lat and user_lng:
            try:
                student_coords = (float(user_lat), float(user_lng))
                hall_coords = (course.latitude, course.longitude)
                distance = geodesic(student_coords, hall_coords).meters

                if distance > course.radius_meters:
                    return render(request, 'quiz/login.html', {
                        'lecturers': Lecturer.objects.all(),
                        'error': f"ACCESS DENIED: You are {round(distance)}m away from the {course.code} exam hall."
                    })
            except ValueError:
                return render(request, 'quiz/login.html', {
                    'lecturers': Lecturer.objects.all(),
                    'error': "Invalid location values received."
                })
        else:
            return render(request, 'quiz/login.html', {
                'lecturers': Lecturer.objects.all(),
                'error': "Location required. Enable GPS in browser settings."
            })

        context = {
            'course': course,
            'questions': Question.objects.filter(course_id=course_id),
            'student_name': full_name,
            'index_number': index_number,
            'duration_ms': course.duration_minutes * 60 * 1000
        }
        return render(request, 'quiz/exam.html', context)
    return redirect('login')


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

        StudentSubmission.objects.create(
            student_name=display_name,
            index_number=index_number,
            course=course_obj,
            submitted_answers=json.dumps(answers),
            score=float(correct_count)
        )

        return render(request, 'quiz/submitted.html', {
            'student_name': full_name,
            'score': int(correct_count),
            'show_score': False if security_breach == "true" else course_obj.show_scores
        })
    return redirect('login')


# ==========================================================
#             ADVANCED BULK IMPORT ENGINE VIEWS
# ==========================================================

def import_questions_page(request):
    """Renders the HTML upload interface page for lecturers."""
    if not request.user.is_staff:
        return redirect('login')

    context = {
        'courses': Course.objects.all()
    }
    return render(request, 'admin/import_questions.html', context)


def import_questions_all_formats(request):
    """Processes document streams, routing parsing logic automatically based on extensions."""
    if request.method != "POST" or not request.FILES.get('uploaded_document'):
        return redirect('login')

    course_id = request.POST.get('course_id')
    course_obj = get_object_or_404(Course, id=course_id)
    uploaded_file = request.FILES['uploaded_document']

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    # Dictionary helper maps document strings smoothly to database choice keys
    QTYPE_MAP = {
        'MCQ': 'MCQ', 'MULTIPLE CHOICE': 'MCQ', 'MULTIPLE_CHOICE': 'MCQ',
        'FITB': 'FITB', 'FILL IN THE BLANK': 'FITB', 'FILL_IN_THE_BLANK': 'FITB',
        'THEORY': 'THEORY', 'WRITTEN ESSAY': 'THEORY', 'ESSAY': 'THEORY'
    }

    try:
        # === 1. DIRECT MICROSOFT EXCEL PARSER (.xlsx) ===
        if ext == '.xlsx':
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
    """Generates a sample .xlsx template file with normalized headers."""
    if not request.user.is_staff:
        return redirect('login')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Question Import Template"

    headers = ['text', 'q_type', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']
    ws.append(headers)

    sample_row = [
        "Example Question: What language is Django written in?",
        "Multiple Choice",
        "Java",
        "Python",
        "C++",
        "PHP",
        "B"
    ]
    ws.append(sample_row)

    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="question_import_blueprint.xlsx"'
    wb.save(response)
    return response


def download_word_template(request):
    """Generates a structured paragraph grid .docx blueprint file container."""
    if not request.user.is_staff:
        return redirect('login')

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