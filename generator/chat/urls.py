from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, MessageViewSet

router = DefaultRouter()
router.register('conversations', ConversationViewSet)
router.register('messages', MessageViewSet)

urlpatterns = router.urls