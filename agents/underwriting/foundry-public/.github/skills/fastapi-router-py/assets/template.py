"""
{{ResourceName}} Router

Handles CRUD operations for {{resource_name}} resources.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.jwt import get_current_user, get_current_user_required
from app.models.{{resource_name}} import (
    {{ResourceName}},
    {{ResourceName}}Create,
    {{ResourceName}}Update,
)
from app.models.user import User
from app.services.{{resource_name}}_service import {{ResourceName}}Service

router = APIRouter(prefix="/api", tags=["{{resource_plural}}"])


def get_service() -> {{ResourceName}}Service:
    """Return the resource service dependency."""
    return {{ResourceName}}Service()


@router.get("/{{resource_plural}}", response_model=list[{{ResourceName}}])
async def list_{{resource_plural}}(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: Optional[User] = Depends(get_current_user),
    service: {{ResourceName}}Service = Depends(get_service),
) -> list[{{ResourceName}}]:
    return await service.list_{{resource_plural}}(limit=limit, offset=offset)


@router.get("/{{resource_plural}}/{{{resource_name}}_id}", response_model={{ResourceName}})
async def get_{{resource_name}}(
    {{resource_name}}_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    service: {{ResourceName}}Service = Depends(get_service),
) -> {{ResourceName}}:
    result = await service.get_{{resource_name}}_by_id({{resource_name}}_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="{{ResourceName}} not found",
        )
    return result


@router.post(
    "/{{resource_plural}}",
    response_model={{ResourceName}},
    status_code=status.HTTP_201_CREATED,
)
async def create_{{resource_name}}(
    data: {{ResourceName}}Create,
    current_user: User = Depends(get_current_user_required),
    service: {{ResourceName}}Service = Depends(get_service),
) -> {{ResourceName}}:
    return await service.create_{{resource_name}}(data, current_user.id)


@router.patch("/{{resource_plural}}/{{{resource_name}}_id}", response_model={{ResourceName}})
async def update_{{resource_name}}(
    {{resource_name}}_id: str,
    data: {{ResourceName}}Update,
    current_user: User = Depends(get_current_user_required),
    service: {{ResourceName}}Service = Depends(get_service),
) -> {{ResourceName}}:
    existing = await service.get_{{resource_name}}_by_id({{resource_name}}_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="{{ResourceName}} not found",
        )
    return await service.update_{{resource_name}}({{resource_name}}_id, data)


@router.delete(
    "/{{resource_plural}}/{{{resource_name}}_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_{{resource_name}}(
    {{resource_name}}_id: str,
    current_user: User = Depends(get_current_user_required),
    service: {{ResourceName}}Service = Depends(get_service),
) -> None:
    existing = await service.get_{{resource_name}}_by_id({{resource_name}}_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="{{ResourceName}} not found",
        )
    await service.delete_{{resource_name}}({{resource_name}}_id)
