# Django feature modules

Feature packages in this folder expose reusable services for account management, report OCR and analysis, chat, doctor/hospital discovery, navigation, reminders, trends, and comparisons. They all use the existing Django models and session; no separate server or database is required.

The shared user-facing HTML, CSS, and JavaScript live in the repository's root `frontend/` directory. Keeping those assets centralized preserves the current theme and avoids duplicated page behavior. Each module README lists its backend entry points.
