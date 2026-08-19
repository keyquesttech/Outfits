from pydantic import BaseModel, Field


class ItemIn(BaseModel):
    name: str = "Untitled item"
    category: str = "top"
    subcategory: str | None = None
    brand: str | None = None
    material: str | None = None
    pattern: str | None = None
    colour_primary: str | None = None
    colour_secondary: str | None = None
    warmth: int = Field(default=5, ge=0, le=10)
    formality: int = Field(default=3, ge=1, le=5)
    seasons: list[str] | None = None
    wind_proof: bool = False
    water_proof: bool = False
    purchase_date: str | None = None
    price: float | None = None
    currency: str = "GBP"
    wash_after_wears: int | None = None
    notes: str | None = None
    tags: list[str] | None = None


class ItemPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    material: str | None = None
    pattern: str | None = None
    colour_primary: str | None = None
    colour_secondary: str | None = None
    warmth: int | None = Field(default=None, ge=0, le=10)
    formality: int | None = Field(default=None, ge=1, le=5)
    seasons: list[str] | None = None
    wind_proof: bool | None = None
    water_proof: bool | None = None
    purchase_date: str | None = None
    price: float | None = None
    currency: str | None = None
    wash_after_wears: int | None = None
    status: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    tags: list[str] | None = None


class CareIn(BaseModel):
    wash_temp: int | None = None
    wash_cycle: str | None = None
    hand_wash_only: bool = False
    do_not_wash: bool = False
    tumble_dry: str | None = None
    iron_temp: str | None = None
    bleach: str | None = None
    dry_clean: str | None = None
    colour_group: str | None = None
    notes: str | None = None


class OutfitIn(BaseModel):
    name: str
    occasion: str | None = None
    notes: str | None = None
    is_favourite: bool = False
    item_ids: list[int] = []


class WearIn(BaseModel):
    item_ids: list[int] = []
    outfit_id: int | None = None
    worn_on: str | None = None
    occasion: str | None = None
    comfort_rating: int | None = Field(default=None, ge=-1, le=1)
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    use_weather: bool = True
    # Supply these when back-filling a past day; current conditions would be wrong.
    temp_c: float | None = None
    apparent_c: float | None = None
    condition: str | None = None


class WashIn(BaseModel):
    item_ids: list[int]
    washed_on: str | None = None
    program: str | None = None
    temp_c: int | None = None
    notes: str | None = None


class StatusIn(BaseModel):
    status: str


class SettingsIn(BaseModel):
    values: dict[str, str]


class WeatherTestIn(BaseModel):
    provider: str | None = None
    # Lets a key be validated before it is saved.
    api_key: str | None = None


class SuggestIn(BaseModel):
    occasion: str | None = None
    count: int = Field(default=3, ge=1, le=8)
    exclude_dirty: bool = True
    seasons: list[str] | None = None
    pinned: list[int] | None = None
    use_ai: bool = False
    day_offset: int = Field(default=0, ge=0, le=4)
