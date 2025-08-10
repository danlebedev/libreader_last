from django.urls import path
from . import views

app_name = 'reader_app'
urlpatterns = [
    # Домашняя страница.
    path('', views.index, name='index'),
    path('book/<int:book_dir>', views.book, name='book'),
    path('book/<int:book_dir>/chapter/<int:chapter_dir>', views.chapter, name='chapter'),
]
