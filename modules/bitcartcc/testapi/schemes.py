from api.schemes import CreatedMixin


class CreateReview(CreatedMixin):
    name: str

    class Config:
        orm_mode = True


class Review(CreateReview):
    id: str
    user_id: str
