from django.contrib import admin
from django.urls import path
from django.core.management import call_command
from django.http import HttpResponse
from django.contrib.auth.models import User
from quiz import views

# Set clear system titles without breaking the framework code structure
admin.site.site_header = "EDEM QUIZ PLATFORM"
admin.site.site_title = "Admin Portal"
admin.site.index_title = "Welcome to the Quiz Admin Engine"

# 🚀 THE BULLETPROOF METHOD: Safely inject global CDN stylesheets into the Admin template
# This hooks directly into Django's official template layout compiler safely!
class GlobalAdminMedia:
    css = {
        'all': ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',)
    }

admin.site.media = GlobalAdminMedia()


# Temporary development function to run migrations and create a superuser over the web
def run_migrations_view(request):
    try:
        # 1. Execute database table migrations on Neon Postgres
        call_command('migrate', interactive=False)

        # 2. Provision admin credentials safely
        username = "admin"
        email = "admin@example.com"
        password = "Titivate12345@$"

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            return HttpResponse("🚀 Database tables built AND Superuser 'admin' created successfully!")

        return HttpResponse("🚀 Database tables built cleanly! Superuser 'admin' already exists.")
    except Exception as e:
        return HttpResponse(f"❌ Error running infrastructure setup: {str(e)}")


urlpatterns = [
    # 0. TEMPORARY DEPLOYMENT TOOLS
    path('run-migrations/', run_migrations_view, name='run_migrations'),

    # 1. CORE ENGINE BULK UPLOAD VIEWS
    path('admin/bulk-import/', views.import_questions_page, name='import_questions_page'),
    path('admin/bulk-import/process/', views.import_questions_all_formats, name='import_questions_all_formats'),

    # 2. BLUEPRINT TEMPLATE DOWNLOAD ACTIONS
    path('admin/bulk-import/download-excel/', views.download_excel_template, name='download_excel_template'),
    path('admin/bulk-import/download-word/', views.download_word_template, name='download_word_template'),

    # 3. MAIN DJANGO ADMIN SCRIPT ENGINE
    path('admin/', admin.site.urls),

    # 4. STUDENT EXAMINATION PLATFORM ENDPOINTS (FIXED ATTRIBUTE ERRORS)
    path('', views.login_portal, name='login_portal'),
    path('login/', views.login_portal, name='login'),
    path('api/get-courses/', views.get_courses, name='get_courses'),
    path('start-quiz/', views.start_quiz, name='start_quiz'),
    path('submit-quiz/', views.submit_quiz, name='submit_quiz'),
# Add this line within the urlpatterns array inside QUIZ1/urls.py
# 🎯 UNIQUE ROUTE: Moves out of the admin/ namespace to prevent routing hijacks
    path('bulk-upload-students/', views.upload_allowed_students, name='upload_allowed_students'),
    path('exam/', views.start_quiz, name='exam_page_url_name'),

]