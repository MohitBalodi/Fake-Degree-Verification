from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter()
api_router.include_router(auth.router)

# Remaining Tier 1 routers are mounted here as they land:
#   institutions, certificates, verify, reviews, share, admin
