import logging
import requests
import pynetbox
from app.config import settings  # Import cấu hình tập trung

# 1. Thiết lập Logging để theo dõi trạng thái
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_netbox_client():
    """Khởi tạo và cấu hình Pynetbox Client an toàn qua class Settings"""
    
    # Không cần check biến môi trường rỗng ở đây nữa, 
    # vì pydantic-settings đã tự động chặn và báo lỗi ngay khi app vừa khởi động nếu thiếu TOKEN.
    try:
        # Khởi tạo client cơ bản
        nb = pynetbox.api(url=settings.NETBOX_URL, token=settings.NETBOX_TOKEN)

        # Cấu hình lại HTTP Session bên dưới của Pynetbox
        session = requests.Session()
        session.verify = settings.NETBOX_SSL_VERIFY
        
        # Bỏ qua cảnh báo InsecureRequestWarning làm rác log nếu tắt verify SSL
        if not settings.NETBOX_SSL_VERIFY:
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning
            )

        # Gắn session đã tối ưu vào client
        nb.http_session = session

        logger.info(f"✅ Đã cấu hình NetBox Client (URL: {settings.NETBOX_URL}, SSL Verify: {settings.NETBOX_SSL_VERIFY})")
        return nb
    
    except Exception as e:
        logger.error(f"❌ Lỗi khi khởi tạo NetBox Client: {e}")
        raise e

# Biến toàn cục để các file route (API) import vào dùng chung
nb_client = init_netbox_client()

def check_netbox_health():
    """
    Hàm tiện ích để kiểm tra "sức khỏe" của NetBox.
    Dùng cho các endpoint Liveness/Readiness Probe của K8s sau này.
    """
    try:
        # Gọi thử một endpoint cực nhẹ không tốn tài nguyên
        status = nb_client.status()
        version = status.get("netbox-version", "Unknown")
        logger.info(f"🟢 Kết nối NetBox ổn định. Phiên bản: {version}")
        return True, version
    except requests.exceptions.ConnectionError:
        logger.error("🔴 Không thể kết nối tới máy chủ NetBox. Kiểm tra lại IP hoặc K8s Service!")
        return False, None
    except pynetbox.core.query.RequestError as e:
        logger.error(f"🔴 Lỗi xác thực hoặc API NetBox từ chối: {e}")
        return False, None
    
def _serialize_device(device) -> dict:
    """
    Hàm helper chuyển đổi Object Device của pynetbox sang Dict thuần để FastAPI xử lý JSON.
    """
    return {
        "id": device.id,
        "name": device.name or f"Device-{device.id}",
        "status": device.status.value if device.status else "N/A",
        "device_type": device.device_type.model if device.device_type else "N/A",
        
        # SỬA Ở ĐÂY: Đổi device.device_role thành device.role
        "device_role": device.role.name if device.role else "N/A",
        
        "site": device.site.name if device.site else "N/A",
        "rack": device.rack.name if device.rack else "N/A",
        "position": device.position,
        "primary_ip": device.primary_ip.address if device.primary_ip else "Chưa cấu hình",
        "tenant": device.tenant.name if device.tenant else "N/A"
    }


def _serialize_vm(vm) -> dict:
    """
    Hàm helper chuyển đổi Object Virtual Machine của pynetbox sang Dict thuần.
    """
    return {
        "id": vm.id,
        "name": vm.name,
        "status": vm.status.value if vm.status else "N/A",
        "cluster_name": vm.cluster.name if vm.cluster else "Mặc định",
        "vcpus": int(vm.vcpus) if vm.vcpus else 0,
        "memory_mb": int(vm.memory) if vm.memory else 0,
        "disk_gb": int(vm.disk) if vm.disk else 0,
        "primary_ip": vm.primary_ip.address if vm.primary_ip else "Chưa cấp IP",
        "tenant": vm.tenant.name if vm.tenant else "N/A"
    }


# ==============================================================================
# 1. CÁC HÀM DÀNH CHO THIẾT BỊ VẬT LÝ (DCIM / DEVICES)
# ==============================================================================

def get_all_devices() -> list:
    """
    [ADMIN] Lấy toàn bộ danh sách thiết bị phần cứng hiện có trên hệ thống NetBox.
    """
    try:
        devices = nb_client.dcim.devices.all()
        return [_serialize_device(d) for d in devices]
    except Exception as e:
        logger.error(f"Lỗi gọi NetBox get_all_devices: {str(e)}")
        raise e


def get_devices_by_tenant(tenant_slug: str) -> list:
    """
    [USER] Lấy danh sách thiết bị phần cứng thuộc sở hữu của một Tenant cụ thể.
    """
    try:
        # Sử dụng phương thức filter của pynetbox với tham số tenant
        devices = nb_client.dcim.devices.filter(tenant=tenant_slug)
        return [_serialize_device(d) for d in devices]
    except Exception as e:
        logger.error(f"Lỗi gọi NetBox get_devices_by_tenant ({tenant_slug}): {str(e)}")
        raise e


# ==============================================================================
# 2. CÁC HÀM DÀNH CHO MÁY ẢO (VIRTUALIZATION / VMS)
# ==============================================================================

def get_all_vms() -> list:
    """
    [ADMIN] Lấy toàn bộ danh sách máy ảo hiện có trên hệ thống vCenter/NetBox.
    """
    try:
        vms = nb_client.virtualization.virtual_machines.all()
        return [_serialize_vm(v) for v in vms]
    except Exception as e:
        logger.error(f"Lỗi gọi NetBox get_all_vms: {str(e)}")
        raise e


def get_vms_by_tenant(tenant_slug: str) -> list:
    """
    [USER] Lấy danh sách máy ảo thuộc phạm vi sở hữu của một Tenant cụ thể.
    """
    try:
        vms = nb_client.virtualization.virtual_machines.filter(tenant=tenant_slug)
        return [_serialize_vm(v) for v in vms]
    except Exception as e:
        logger.error(f"Lỗi gọi NetBox get_vms_by_tenant ({tenant_slug}): {str(e)}")
        raise e