from django.contrib import admin
from django.urls import path
from chat.views import chat_view, karar_ara_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/chat/', chat_view),
    path('api/karar-ara/', karar_ara_view),
]