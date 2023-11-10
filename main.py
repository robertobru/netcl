from fastapi import FastAPI
from rest_endpoints.rest_switch import netmgt_router

app = FastAPI(
    title="NetCL",
    # description=description,
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

app.include_router(netmgt_router)
