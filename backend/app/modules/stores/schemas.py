"""
Pydantic schemas for competitor store endpoints.
"""


from pydantic import BaseModel, Field, field_validator


class AddStoreRequest(BaseModel):
    url: str = Field(
        min_length=3,
        max_length=2048,
        description="Competitor Shopify store URL (e.g. https://example.myshopify.com)",
    )
    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional human-readable name for this store",
    )

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class StoreResponse(BaseModel):
    id: str
    url: str
    display_name: str | None
    platform: str
    status: str
    last_error: str | None
    last_discovery_at: str | None
    products_count: int = 0
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, store: object, products_count: int = 0) -> "StoreResponse":
        from app.modules.stores.models import CompetitorStore
        assert isinstance(store, CompetitorStore)
        return cls(
            id=str(store.id),
            url=store.url,
            display_name=store.display_name,
            platform=store.platform,
            status=store.status,
            last_error=store.last_error,
            last_discovery_at=(
                store.last_discovery_at.isoformat() if store.last_discovery_at else None
            ),
            products_count=products_count,
            created_at=store.created_at.isoformat(),
        )



class StoreListResponse(BaseModel):
    stores: list[StoreResponse]
    total: int
