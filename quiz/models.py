import json
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ==========================================
# 1. LECTURER MODEL
# ==========================================
class Lecturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=20)

    def __str__(self):
        if self.user.get_full_name():
            return f"Dr. {self.user.get_full_name()}"
        return f"Dr. {self.user.username}"


# ==========================================
# 2. COURSE MODEL
# ==========================================
class Course(models.Model):
    ASSESSMENT_TYPES = [
        ('QUIZ', 'Quiz / Continuous Assessment'),
        ('ASSIGNMENT', 'Take-Home Assignment'),
        ('MIDSEM', 'Mid-Semester Examination'),
        ('PROJECT', 'Project Submission'),
        ('FINAL', 'End of Semester Exam'),
    ]

    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)  # e.g., "SIGNALS AND SYSTEMS"
    code = models.CharField(max_length=200)  # e.g., "ELNG 222"

    # 🆕 NEW: Assessment Category Selector
    assessment_type = models.CharField(
        max_length=20,
        choices=ASSESSMENT_TYPES,
        default='QUIZ'  # Protects existing database entries during migration
    )

    exam_name = models.CharField(max_length=200, help_text="e.g., Quiz 1, Midsem, Project Phase 1")
    duration_minutes = models.IntegerField(default=30)

    # Geofencing Parameters
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_meters = models.FloatField(default=100)

    show_scores = models.BooleanField(default=False)

    # === DATETIME WINDOW CONTROLS ===
    start_time = models.DateTimeField(default=timezone.now, help_text="When students can begin logging in.")
    end_time = models.DateTimeField(default=timezone.now, help_text="When the entry portal closes completely.")

    def __str__(self):
        # Displays beautifully in Django Admin: "ELNG 222 - Midsem (Mid-Semester Examination)"
        return f"{self.code} - {self.exam_name} ({self.get_assessment_type_display()})"
# ==========================================
# 3. QUESTION MODEL (WITH BUILT-IN IMPORT NORMALIZER)
# ==========================================
class Question(models.Model):
    QUESTION_TYPES = [
        ('MCQ', 'Multiple Choice'),
        ('FITB', 'Fill in the Blank'),
        ('THEORY', 'Written Essay'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    text = models.TextField()

    # Expanded length constraints to ensure loose type boundaries match code layout
    q_type = models.CharField(max_length=200, choices=QUESTION_TYPES, default='MCQ')

    # MCQ Options
    option_a = models.CharField(max_length=255, blank=True, null=True)
    option_b = models.CharField(max_length=255, blank=True, null=True)
    option_c = models.CharField(max_length=255, blank=True, null=True)
    option_d = models.CharField(max_length=255, blank=True, null=True)

    correct_answer = models.CharField(max_length=255)

    def __str__(self):
        return self.text[:50]

    def save(self, *args, **kwargs):
        """
        🚀 SAFE NORMALIZATION INTERCEPTOR
        Automatically cleans and maps long excel strings to database keys
        before saving to prevent character varying(10) production crashes.
        """
        if self.q_type:
            # Clean string spaces and force title casing to match variations
            clean_type = str(self.q_type).strip().title()

            if clean_type in ['Multiple Choice', 'Mcq', 'M']:
                self.q_type = 'MCQ'
            elif clean_type in ['Fill In The Blank', 'Fitb', 'F']:
                self.q_type = 'FITB'
            elif clean_type in ['Written Essay', 'Writtenessay', 'Theory', 'Essay', 'T', 'E']:
                self.q_type = 'THEORY'

        super(Question, self).save(*args, **kwargs)


# ==========================================
# 4. STUDENT SUBMISSION MODEL
# ==========================================
class StudentSubmission(models.Model):
    student_name = models.CharField(max_length=100)
    index_number = models.CharField(max_length=20)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    submitted_answers = models.TextField(null=True, blank=True)
    score = models.FloatField(default=0.0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student_name} - {self.course.code}"


# ==========================================
# 5. ENFORCED ACCESS CONTROL MODEL (FIXED ALIGNMENT)
# ==========================================
class AllowedStudent(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    index_number = models.CharField(max_length=20)
    full_name = models.CharField(max_length=100)
    has_taken_exam = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['index_number', 'course'], name='unique_student_per_course')
        ]

    def __str__(self):
        return f"{self.index_number} - {self.full_name}"