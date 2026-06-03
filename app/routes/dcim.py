from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Gộp chung các Import tương đối (Relative Imports) cho chuẩn kiến trúc
from .. import models, utils
from ..netbox_client import nb_client
from ..database import get_db
from .auth import get_current_user

# Khởi tạo Router
router = APIRouter(prefix="/api/v1/dcim", tags=["DCIM (Physical Infrastructure)"])

# ==========================================
# 1. API: QUẢN LÝ SITES (DATA CENTERS)
# ==========================================
@router.get("/sites")
def get_all_sites(admin_user: models.User = Depends(utils.require_admin)):
    """[ADMIN] Lấy danh sách các Data Center / Site vật lý từ NetBox"""
    try:
        sites = nb_client.dcim.sites.all()
        # Bắt buộc dùng getattr để tránh lỗi nếu trường đó rỗng (None) trong NetBox
        results = [{"id": s.id, "name": s.name, "slug": s.slug, "status": s.status.value if getattr(s, 'status', None) else "Unknown", "facility": s.facility or "N/A"} for s in sites]
        return {"total": len(results), "sites": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 2. API: QUẢN LÝ RACKS (TỦ MẠNG)
# ==========================================
@router.get("/racks")
def get_all_racks(site_slug: str = None, admin_user: models.User = Depends(utils.require_admin)):
    """[ADMIN] Lấy danh sách Tủ Rack."""
    try:
        racks = nb_client.dcim.racks.filter(site=site_slug) if site_slug else nb_client.dcim.racks.all()
        results = [{"id": r.id, "name": r.name, "site": r.site.name if getattr(r, 'site', None) else "N/A", "status": r.status.value if getattr(r, 'status', None) else "Unknown", "role": r.role.name if getattr(r, 'role', None) else "N/A", "u_height": r.u_height} for r in racks]
        return {"total": len(results), "racks": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 3. API: QUẢN LÝ THIẾT BỊ VẬT LÝ (DEVICES)
# ==========================================
@router.get("/devices")
def get_devices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """[ALL] Lấy danh sách thiết bị. Lọc theo Tenant nếu là User thường."""
    user_role = current_user.role.name.upper() if current_user.role else "USER"
    query_params = {}
    
    # Nếu là USER, thiết lập tham số lọc (query_params)
    if user_role != "ADMIN":
        if not current_user.customer_id:
            return {"devices": []}
            
        customer = db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).first()
        if not customer or not customer.tenant_slug:
            return {"devices": []}
            
        query_params['tenant'] = customer.tenant_slug

    try:
        # Gọi trực tiếp pynetbox để lấy dữ liệu
        devices_raw = nb_client.dcim.devices.filter(**query_params) if query_params else nb_client.dcim.devices.all()
        
        # MAPPING DỮ LIỆU: Bắt buộc để tránh lỗi Object Not JSON Serializable
        results = []
        for dev in devices_raw:
            results.append({
                "id": dev.id,
                "name": dev.name,
                "device_type": dev.device_type.model if getattr(dev, 'device_type', None) else "Unknown",
                "device_role": dev.device_role.name if getattr(dev, 'device_role', None) else "Unknown",
                "tenant": dev.tenant.name if getattr(dev, 'tenant', None) else "None",
                "site": dev.site.name if getattr(dev, 'site', None) else "Unknown",
                "rack": dev.rack.name if getattr(dev, 'rack', None) else "N/A",
                "position": dev.position,
                "primary_ip": dev.primary_ip.address if getattr(dev, 'primary_ip', None) else "N/A",
                "status": dev.status.value if getattr(dev, 'status', None) else "Unknown"
            })
        return {"devices": results}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Hệ thống lỗi khi truy xuất dữ liệu từ NetBox: {str(e)}"
        )

# ==========================================
# 4. API: CHI TIẾT THIẾT BỊ VẬT LÝ
# ==========================================
@router.get("/devices/{device_id}")
def get_device_details(
    device_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user) # Đã sửa thành get_current_user thay vì require_admin
):
    """[ALL] Lấy thông tin chi tiết thiết bị kèm interfaces. User chỉ xem được thiết bị của mình."""
    try:
        dev = nb_client.dcim.devices.get(device_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị.")

        # KIỂM TRA QUYỀN TRUY CẬP (BẢO MẬT)
        user_role = current_user.role.name.upper() if current_user.role else "USER"
        if user_role != "ADMIN":
            customer = db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).first()
            if not customer or getattr(dev, 'tenant', None) is None or dev.tenant.slug != customer.tenant_slug:
                raise HTTPException(status_code=403, detail="Cảnh báo an ninh: Không có quyền xem thiết bị này.")

        # Lấy thông tin Interfaces (Cổng mạng)
        interfaces = nb_client.dcim.interfaces.filter(device_id=device_id)
        if_list = [{"id": i.id, "name": i.name, "type": i.type.value if getattr(i, 'type', None) else "Unknown", "enabled": i.enabled, "mac_address": i.mac_address or "N/A"} for i in interfaces]

        # Trả về JSON đã được Mapping sạch sẽ
        return {
            "id": dev.id, 
            "name": dev.name, 
            "serial": dev.serial or "N/A", 
            "device_type": dev.device_type.model if getattr(dev, 'device_type', None) else "Unknown",
            "device_role": dev.device_role.name if getattr(dev, 'device_role', None) else "Unknown",
            "site": dev.site.name if getattr(dev, 'site', None) else "Unknown",
            "rack": dev.rack.name if getattr(dev, 'rack', None) else "N/A",
            "position": dev.position,
            "tenant": dev.tenant.name if getattr(dev, 'tenant', None) else "None",
            "status": dev.status.value if getattr(dev, 'status', None) else "Unknown", 
            "primary_ip": dev.primary_ip.address if getattr(dev, 'primary_ip', None) else "N/A",
            "interfaces_count": len(if_list), 
            "interfaces": if_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(e)}")