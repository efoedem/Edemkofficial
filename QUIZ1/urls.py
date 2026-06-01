from django.contrib import admin
from django.urls import path
from quiz import views

urlpatterns = [
    # 1. CORE ENGINE BULK UPLOAD VIEWS
    path('admin/bulk-import/', views.import_questions_page, name='import_questions_page'),
    path('admin/bulk-import/process/', views.import_questions_all_formats, name='import_questions_all_formats'),

    # 2. BLUEPRINT TEMPLATE DOWNLOAD ACTIONS
    path('admin/bulk-import/download-excel/', views.download_excel_template, name='download_excel_template'),
    path('admin/bulk-import/download-word/', views.download_word_template, name='download_word_template'),

    # 3. MAIN DJANGO ADMIN SCRIPT ENGINE
    path('admin/', admin.site.urls),

    # 4. STUDENT EXAMINATION PLATFORM ENDPOINTS
    path('', views.login_page, name='login'),
    path('api/get-courses/', views.get_courses, name='get_courses'),
    path('start-quiz/', views.start_quiz, name='start_quiz'),
    path('submit-quiz/', views.submit_quiz, name='submit_quiz'),
]