import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from . import models
from .routes import system, auth, iam, business, virtualization, billing
from .routes import dcim_safe as dcim
from .routes import ipam_safe as ipam

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Suncloud Management API",
    description="Backend Service tích hợp NetBox và Quản lý Kinh doanh",
    version="1.0.0",
)


@app.get("/")
def read_root():
    return {"message": "Chào mừng đến với Suncloud Management API!"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://172.16.66.82",
        "http://172.16.66.82:5500",
        "http://172.16.66.82:8000",
        "http://localhost",
        "http://localhost:5500",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(iam.router)
app.include_router(business.router)
app.include_router(dcim.router)
app.include_router(virtualization.router)
app.include_router(ipam.router)
app.include_router(billing.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
