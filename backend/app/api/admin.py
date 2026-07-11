from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminUserPublic,
    AnalyticsSummary,
    ApiUsageLogPublic,
    AuditLogPublic,
    UserDetailPublic,
)
from app.services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserPublic])
async def list_users(
    search: str | None = None,
    role: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users, _total = await admin_service.list_users(db, search=search, role=role, limit=limit, offset=offset)
    return users


@router.get("/users/{user_id}", response_model=UserDetailPublic)
async def get_user_detail(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        detail = await admin_service.get_user_detail(db, user_id=user_id)
    except admin_service.UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    user = detail.pop("user")
    user_data = AdminUserPublic.model_validate(user).model_dump()
    return UserDetailPublic(**user_data, **detail)


@router.post("/users/{user_id}/suspend", response_model=AdminUserPublic)
async def suspend_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await admin_service.suspend_user(db, admin_id=admin.id, user_id=user_id)
    except admin_service.CannotModifySelfError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except admin_service.UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/users/{user_id}/unsuspend", response_model=AdminUserPublic)
async def unsuspend_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await admin_service.unsuspend_user(db, user_id=user_id)
    except admin_service.UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await admin_service.delete_user(db, admin_id=admin.id, user_id=user_id)
    except admin_service.CannotModifySelfError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except admin_service.UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/analytics", response_model=AnalyticsSummary)
async def get_analytics(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_analytics_summary(db)


@router.get("/logs/api-usage", response_model=list[ApiUsageLogPublic])
async def get_api_usage_logs(
    limit: int = 100,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_api_usage_logs(db, limit=limit, offset=offset)


@router.get("/logs/errors", response_model=list[ApiUsageLogPublic])
async def get_error_logs(
    limit: int = 100,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_error_logs(db, limit=limit, offset=offset)


@router.get("/logs/audit", response_model=list[AuditLogPublic])
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_audit_logs(db, limit=limit, offset=offset)
