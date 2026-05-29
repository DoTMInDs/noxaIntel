from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from services.ai_chat_service import AIChatService

@login_required
def assistant_chat(request):
    """Renders the main AI Assistant chat interface with historic conversation logs."""
    history = AIChatService.get_conversation_history(request.user.id)
    return render(request, 'ai_engine/assistant.html', {'history': history})

@login_required
def assistant_query(request):
    """HTMX endpoint handling user chat messages and returning AI responses."""
    user_message = request.POST.get('message', '').strip()
    if not user_message:
        return render(request, 'ai_engine/partials/chat_message.html', {
            'error': "Please enter a question."
        })

    ai_response = AIChatService.generate_response(user_message, request.user)

    return render(request, 'ai_engine/partials/chat_message.html', {
        'user_message': user_message,
        'ai_response': ai_response,
    })

