from api.models import BaseModel, Column, DateTime, ForeignKey, Text, User


class PluginBaseModel(BaseModel):
    TABLE_PREFIX = "testapi"


class Reviews(PluginBaseModel):
    __tablename__ = "reviews"

    id = Column(Text, primary_key=True, index=True)
    name = Column(Text)
    created = Column(DateTime(True), nullable=False)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
