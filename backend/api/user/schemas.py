"""DTO for user management"""

from pydantic import BaseModel, ConfigDict

from api.user.models import Roles


class User(BaseModel):
    """Schema for create new user"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    password: str
    role: Roles


class UserForm(BaseModel):
    username: str
    password: str
    role: Roles
