from django.urls import re_path
from chat.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(
        r'^api/ws/chat/conversations/(?P<conversation_id>\w+)/$',
        ChatConsumer.as_asgi(),
    ),
]
