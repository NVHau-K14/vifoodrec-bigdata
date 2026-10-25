"""Schema Pydantic cua response (hien o /docs).

response_model loc bo moi truong khong khai bao: UserOut khong co truth, nen du truy van co sot thi
API cung khong tra persona that (D14 cau 4, D15).
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Source = Literal["als", "content_slot", "pop", "fill", "rep", "content"]
Dot = Literal["herb", "chili", "neutral"]


class DishCard(BaseModel):
    food_id: int
    dish_name: str
    image_link: Optional[str] = None
    dish_category: Optional[str] = None
    dish_type_fixed: Optional[str] = None
    is_vegetarian: bool = False
    is_quick: bool = False
    is_spicy: bool = False
    meal_types: list[str] = []


class DishRanked(DishCard):
    cooks: Optional[int] = Field(None, description="lượt nấu cả năm mô phỏng (dishes.stats)")
    cook_rank: Optional[int] = None


class DishList(BaseModel):
    total: int
    items: list[DishRanked]


class Because(BaseModel):
    food_id: int
    dish_name: Optional[str] = None


class RecItem(DishCard):
    rank: int
    rec_rank: Optional[int] = Field(None, description="hạng trong 50 món gợi ý; null với món bù")
    source: Source
    dot: Dot
    reason: str
    because: Optional[Because] = None
    hit: Optional[bool] = Field(None, description="món có trong lượt nấu tháng 9/2026 (test_cooks)")


class RecSummary(BaseModel):
    from_recs: int
    from_fill: int
    from_popular: int = 0
    hits: Optional[int] = None
    n_test_cooks: Optional[int] = None


class RecsOut(BaseModel):
    user_id: Optional[int] = None
    filters: dict[str, Any]
    items: list[RecItem]
    summary: RecSummary


class NewUserIn(BaseModel):
    food_ids: list[int] = Field(..., min_length=1, max_length=10, description="1–10 món người dùng thích")
    region: Optional[Literal["Bắc", "Trung", "Nam"]] = None
    age_group: Optional[Literal["18-24", "25-34", "35-44", "45+"]] = None
    limit: int = Field(10, ge=1, le=20)
    veg: bool = False
    quick: bool = False
    not_spicy: bool = False
    meal: Optional[Literal["sáng", "trưa", "tối", "ăn vặt"]] = None
    category: Optional[str] = None


class Profile(BaseModel):
    n_events: Optional[int] = None
    n_cook: Optional[int] = None
    n_rate: Optional[int] = None
    avg_rating: Optional[float] = None
    share_chay: Optional[float] = None
    share_haisan: Optional[float] = None
    share_ngot: Optional[float] = None
    share_nhanh: Optional[float] = None
    share_cay: Optional[float] = None
    pref_slot: Optional[str] = None


class HistoryItem(DishCard):
    n_cook: int
    last_cook: Optional[str] = None


class UserOut(BaseModel):
    user_id: int
    region: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    group: Optional[str] = None
    cluster_k8: Optional[int] = None
    profile: Optional[Profile] = None
    history: list[HistoryItem] = []
    n_test_cooks: int = 0


class DemoUser(BaseModel):
    user_id: int
    group: Optional[str] = None
    region: Optional[str] = None
    age_group: Optional[str] = None
    n_cook: Optional[int] = None


class PersonaUsers(BaseModel):
    persona: str
    verify_only: bool = True
    users: list[DemoUser]


class DemoUsersOut(BaseModel):
    by_group: dict[str, list[DemoUser]]
    by_persona: list[PersonaUsers] = Field(description="persona thật, chỉ để kiểm chứng (verify_only)")
    verify_only: bool = True


class SimilarDish(DishCard):
    sim: float


class CompanionDish(DishCard):
    confidence: float
    lift: float


class DishDetail(DishCard):
    ingredient_list: list[str] = []
    ingredients: Optional[str] = None
    preparation: Optional[str] = None
    cooking_method: Optional[str] = None
    serving_size: Optional[int] = None
    source: Optional[str] = None
    season: Optional[str] = None
    main_protein: Optional[str] = None
    main_method: Optional[str] = None
    stats: Optional[dict[str, Any]] = Field(None, description="thống kê cả năm mô phỏng")
    companions: list[CompanionDish] = []
    similar: list[SimilarDish] = []
