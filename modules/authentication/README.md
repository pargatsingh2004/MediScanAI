# Authentication module

This module uses Django's configured user model, session middleware, and the shared healthcare profile. `backend/services/account_service.py` creates inactive accounts and verifies one-time email codes. Password-reset and account endpoints remain compatible with the existing workspace routes.
