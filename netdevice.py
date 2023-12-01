from pydantic import BaseModel, SecretStr, field_serializer
from typing import Optional


class Device(BaseModel):
    name: str
    model: str
    user: Optional[str]
    passwd: Optional[SecretStr]
    address: str

    @field_serializer('passwd', when_used='json')
    def dump_secret(self, v):
        return v.get_secret_value()
