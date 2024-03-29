from fastapi import FastAPI
from rest_endpoints.rest_switch import device_api_router
from rest_endpoints.rest_network import net_api_router
from rest_endpoints.rest_operation import operation_router
#import uvicorn

app = FastAPI(
    title="NetCL",
    # description=description,
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

app.include_router(device_api_router)
app.include_router(net_api_router)
app.include_router(operation_router)

#uvicorn.run(app, host="127.0.0.1", port=8080)