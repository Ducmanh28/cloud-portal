import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings  # Import cấu hình tập trung

# 1. Thiết lập Logging để dễ debug trong K8s
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Khởi tạo Engine với các tham số tối ưu cho Production
try:
    engine = create_engine(
        settings.database_url,   # Lấy chuỗi kết nối an toàn từ class Settings
        pool_pre_ping=True,      # Kiểm tra kết nối (ping) trước khi query, tránh lỗi rớt mạng ngầm
        pool_size=10,            # Số lượng kết nối duy trì thường trực (phù hợp với test/vừa)
        max_overflow=20,         # Cho phép mở rộng thêm tối đa 20 kết nối khi bị quá tải request
        pool_recycle=3600,       # Tự động làm mới kết nối sau mỗi 1 giờ (MySQL mặc định ngắt sau 8h)
        echo=False               # Đổi thành True nếu muốn soi các câu SQL thô in ra terminal
    )
    logger.info("✅ Đã cấu hình Database Engine thành công thông qua config.")
except Exception as e:
    logger.error(f"❌ Lỗi cấu hình Database: {e}")
    raise e

# 3. Khởi tạo Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Khởi tạo Base Model
Base = declarative_base()

# 5. Dependency Database cho FastAPI
def get_db():
    """
    Hàm này tạo một phiên làm việc (session) với DB cho mỗi Request gọi tới API.
    Sau khi trả kết quả cho User, nó sẽ tự động đóng kết nối (finally: db.close())
    để giải phóng tài nguyên.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()