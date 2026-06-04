import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import Database & Models
from .database import engine
from . import models

# Import tất cả các Router từ thư mục routes
from .routes import (
    system,
    auth,
    iam,
    business,
    dcim,
    virtualization,
    ipam,
    billing,
)

# 1. Khởi tạo Database (Tự động tạo bảng nếu chưa có)
models.Base.metadata.create_all(bind=engine)

# 2. Khởi tạo ứng dụng FastAPI tổng
app = FastAPI(
    title="Suncloud Management API",
    description="Backend Service tích hợp NetBox và Quản lý Kinh doanh",
    version="1.0.0",
)


@app.get("/")
def read_root():
    return {"message": "Chào mừng đến với Suncloud Management API!"}


# 3. Cấu hình Middleware (CORS - Cho phép Frontend gọi API)
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

# 4. Gắn (Mount) tất cả các API từ các file bên ngoài vào App chính
app.include_router(system.router)          # /health
app.include_router(auth.router)            # /api/v1/auth/*
app.include_router(iam.router)             # /api/v1/iam/*
app.include_router(business.router)        # /api/v1/business/*
app.include_router(dcim.router)            # /api/v1/dcim/*
app.include_router(virtualization.router)  # /api/v1/virtualization/*
app.include_router(ipam.router)            # /api/v1/ipam/*
app.include_router(billing.router)         # /api/v1/billing/*

# 5. Khối lệnh chạy trực tiếp
if __name__ == "__main__":
    # Chạy ứng dụng tại http://0.0.0.0:8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
