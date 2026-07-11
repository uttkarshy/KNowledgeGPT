from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.knowledge_base import (
    CreateKnowledgeBaseRequest,
    KnowledgeBasePublic,
    KnowledgeBaseStats,
    UpdateKnowledgeBaseRequest,
)
from app.services import knowledge_base_service

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


@router.post("", response_model=KnowledgeBasePublic, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_base_service.create_knowledge_base(db, owner_id=current_user.id, body=body)


@router.get("", response_model=list[KnowledgeBasePublic])
async def list_knowledge_bases(
    include_archived: bool = False,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_base_service.list_knowledge_bases(
        db, owner_id=current_user.id, include_archived=include_archived, search=search
    )


@router.get("/{kb_id}", response_model=KnowledgeBasePublic)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await knowledge_base_service.get_owned_knowledge_base(db, kb_id=kb_id, owner_id=current_user.id)
    except knowledge_base_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/{kb_id}", response_model=KnowledgeBasePublic)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    body: UpdateKnowledgeBaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await knowledge_base_service.update_knowledge_base(
            db, kb_id=kb_id, owner_id=current_user.id, body=body
        )
    except knowledge_base_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{kb_id}/archive", response_model=KnowledgeBasePublic)
async def archive_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await knowledge_base_service.archive_knowledge_base(db, kb_id=kb_id, owner_id=current_user.id)
    except knowledge_base_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{kb_id}/duplicate", response_model=KnowledgeBasePublic, status_code=status.HTTP_201_CREATED)
async def duplicate_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await knowledge_base_service.duplicate_knowledge_base(db, kb_id=kb_id, owner_id=current_user.id)
    except knowledge_base_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/{kb_id}/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await knowledge_base_service.get_knowledge_base_stats(db, kb_id=kb_id, owner_id=current_user.id)
    except knowledge_base_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await knowledge_base_service.delete_knowledge_base(db, kb_id=kb_id, owner_id=current_user.id)
    except knowledge_base_service.KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
