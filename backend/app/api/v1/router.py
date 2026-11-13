from fastapi import APIRouter

from app.api.v1 import auth, certificates

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(certificates.router)

# Remaining Tier 1 routers are mounted here as they land:
#   institutions, verify, reviews, share, admin
