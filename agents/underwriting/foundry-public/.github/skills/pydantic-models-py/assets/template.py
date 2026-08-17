"""
{{ResourceName}} Models

Pydantic models for {{resource_name}} using the multi-model pattern.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class {{ResourceName}}Base(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name for the {{resource_name}}",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Optional description",
    )

    class Config:
        populate_by_name = True


class {{ResourceName}}Create({{ResourceName}}Base):
    workspace_id: str = Field(
        ...,
        alias="workspaceId",
        description="ID of the parent workspace",
    )


class {{ResourceName}}Update(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)

    class Config:
        populate_by_name = True


class {{ResourceName}}({{ResourceName}}Base):
    id: str = Field(..., description="Unique identifier")
    slug: str = Field(..., description="URL-friendly identifier")
    workspace_id: str = Field(..., alias="workspaceId")
    author_id: str = Field(..., alias="authorId")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


class {{ResourceName}}InDB({{ResourceName}}):
    doc_type: str = "{{resource_name}}"
