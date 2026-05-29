from fastapi import APIRouter
from ..netbox_client import check_netbox_health

router = APIRouter(tags=["System Monitor"])

@router.get("/health")
def health_check():
    """Kiểm tra sức khỏe tổng thể của Backend và các hệ thống vệ tinh (NetBox, MySQL)"""
    nb_status, nb_version = check_netbox_health()
    return {
        "service": "Suncloud Backend",
        "status": "UP",
        "netbox_connected": nb_status,
        "netbox_version": nb_version
    }