import csv
from django.http import HttpResponse
from django.contrib import admin
from .models import Lecturer, Course, Question, StudentSubmission, AllowedStudent


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'course', 'get_exam_name', 'q_type')
    list_filter = ('course', 'course__exam_name', 'q_type')
    search_fields = ('text',)

    # Points Django to read our button injector template when rendering the questions list table
    change_list_template = "admin/quiz/question/change_list.html"

    def get_exam_name(self, obj):
        return obj.course.exam_name

    get_exam_name.short_description = 'Exam Type'


@admin.register(StudentSubmission)
class StudentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'index_number', 'course', 'get_exam_name', 'score', 'submitted_at')
    list_filter = ('course', 'course__exam_name')
    search_fields = ('student_name', 'index_number')
    actions = ['export_to_csv']

    def get_exam_name(self, obj):
        return obj.course.exam_name

    get_exam_name.short_description = 'Exam Type'

    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_results.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student Name', 'Index Number', 'Course', 'Exam Type', 'Score', 'Submitted At'])
        for obj in queryset:
            writer.writerow([
                obj.student_name, obj.index_number, obj.course.title,
                obj.course.exam_name, obj.score, obj.submitted_at.strftime("%Y-%m-%d %H:%M")
            ])
        return response

    export_to_csv.short_description = "Download Selected as Excel (CSV)"



    @admin.register(Course)
    class CourseAdmin(admin.ModelAdmin):
        list_display = ('code', 'title', 'exam_name', 'duration_minutes', 'start_time', 'end_time')
        list_filter = ('lecturer', 'start_time')
        search_fields = ('code', 'title')

        # === Tells Django to use our upcoming template override for Course forms ===
        change_form_template = "admin/quiz/course/change_form.html"


@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ('user', 'staff_id')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'staff_id')


    # This custom admin layout makes managing student lists incredibly easy
    @admin.register(AllowedStudent)
    class AllowedStudentAdmin(admin.ModelAdmin):
        # Columns that show up on the main list dashboard view
        list_display = ('index_number', 'full_name', 'course', 'has_taken_exam')

        # Filter tools on the right sidebar to sort students by exam group
        list_filter = ('course', 'has_taken_exam')

        # Quick search bar at the top to find an index number instantly
        search_fields = ('index_number', 'full_name')

    # Keep your existing admin registrations here as well:
    admin.site.register(Lecturer)
    admin.site.register(Course)
    admin.site.register(Question)
    admin.site.register(StudentSubmission)