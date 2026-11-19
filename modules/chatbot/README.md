# Chatbot module

`backend/services/chat_service.py` exposes report-grounded answers and reply rewrites. It uses the shared analysis prompt and stores conversation records through the existing Django workspace endpoints. Report access remains scoped to the signed-in user.

The existing workspace HTML, CSS, and JavaScript remain the single front-end source so its theme and behavior stay consistent.
