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
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)  # Standardized max_length
    code = models.CharField(max_length=200)    # Standardized max_length
    exam_name = models.CharField(max_length=200) # Standardized max_length
    duration_minutes = models.IntegerField(default=30)

    # Geofencing Parameters
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_meters = models.FloatField(default=100)

    show_scores = models.BooleanField(default=False)

    # === NEW DATETIME WINDOW CONTROLS ===
    start_time = models.DateTimeField(default=timezone.now, help_text="When students can begin logging in.")
    end_time = models.DateTimeField(default=timezone.now, help_text="When the entry portal closes completely.")

    def __str__(self):
        return f"{self.code} - {self.title}"


# ==========================================
# 3. QUESTION MODEL
# ==========================================
class Question(models.Model):
    QUESTION_TYPES = [
        ('MCQ', 'Multiple Choice'),
        ('FITB', 'Fill in the Blank'),
        ('THEORY', 'Written Essay'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    text = models.TextField()
    q_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default='MCQ')

    # MCQ Options
    option_a = models.CharField(max_length=255, blank=True, null=True)
    option_b = models.CharField(max_length=255, blank=True, null=True)
    option_c = models.CharField(max_length=255, blank=True, null=True)
    option_d = models.CharField(max_length=255, blank=True, null=True)

    correct_answer = models.CharField(max_length=255)

    def __str__(self):
        return self.text[:50]


# ==========================================
# 4. STUDENT SUBMISSION MODEL
# ==========================================
class StudentSubmission(models.Model):
    student_name = models.CharField(max_length=100)
    index_number = models.CharField(max_length=20)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    submitted_answers = models.TextField(null=True, blank=True)
    score = models.FloatField(default=0.0)
    submitted_at = models.DateTimeField(auto_now_add=True) # Unified field naming string

    def __str__(self):
        return f"{self.student_name} - {self.course.code}"