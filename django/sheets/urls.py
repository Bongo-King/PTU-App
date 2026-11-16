from django.urls import path
from . import views

app_name = "sheets"
urlpatterns = [
    path("", views.sheet_list, name="list"),
    path("<int:pk>/values/", views.edit_value, name="edit_value"),
    path("<int:pk>/form/", views.switch_form, name="switch_form"),
    path("<int:pk>/", views.sheet_detail, name="detail"),
]
