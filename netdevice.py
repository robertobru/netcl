from __future__ import annotations
from pydantic import BaseModel, SecretStr, field_serializer
from typing import Optional


class Device(BaseModel):
    name: str
    model: str
    user: Optional[str]
    passwd: Optional[SecretStr]
    address: str
    client_id: Optional[str] = None
    key: Optional[str] = None

    """class Config:
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value(),
        }"""

    @field_serializer('passwd', when_used='json')
    def dump_secret(self, v):
        return v.get_secret_value() #  if type[v] is SecretStr else v

    def to_device_model(self) -> Device:
        return Device.model_validate(self, from_attributes=True)
