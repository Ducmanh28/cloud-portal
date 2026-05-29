from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, netbox_client  # Thay thế theo cụm import thực tế của bạn
from app.database import get_db
from app.routes.auth import get_current_user
# Import module nội bộ từ thư mục cha
from .. import models, utils
from ..netbox_client import nb_client

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
        results = [{"id": s.id, "name": s.name, "slug": s.slug, "status": s.status.value if s.status else "Unknown", "facility": s.facility or "N/A"} for s in sites]
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
        results = [{"id": r.id, "name": r.name, "site": r.site.name if r.site else "N/A", "status": r.status.value if r.status else "Unknown", "role": r.role.name if r.role else "N/A", "u_height": r.u_height} for r in racks]
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
    # Truy vấn trực tiếp từ Database để đảm bảo tính chính xác, tránh lỗi nghẽn Lazy Loading
    role = db.query(models.Role).filter(models.Role.id == current_user.role_id).first()
    user_role = role.name.upper() if role else "USER"
    
    # ----------------------------------------------------------------------
    # LUỒNG XỬ LÝ 1: DÀNH CHO QUỒN ADMIN (XEM TOÀN BỘ)
    # ----------------------------------------------------------------------
    if user_role == "ADMIN":
        try:
            # Gọi hàm không truyền tham số filter để lấy toàn bộ danh sách thiết bị trên NetBox
            devices = netbox_client.get_all_devices()
            return {"devices": devices}
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Hệ thống lỗi khi Admin truy xuất toàn bộ dữ liệu NetBox: {str(e)}"
            )
            
    # ----------------------------------------------------------------------
    # LUỒNG XỬ LÝ 2: DÀNH CHO USER THƯỜNG (LỌC THEO TENANT)
    # ----------------------------------------------------------------------
    if not current_user.customer_id:
        raise HTTPException(
            status_code=400, 
            detail="Tài khoản thường chưa được liên kết với bất kỳ tổ chức/khách hàng nào."
        )
        
    customer = db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).first()
    if not customer or not customer.tenant_slug:
        raise HTTPException(
            status_code=444, 
            detail="Không tìm thấy cấu hình mã Tenant (tenant_slug) của khách hàng."
        )
        
    try:
        # Lọc nghiêm ngặt, chỉ trả về các thiết bị gán nhãn tenant_slug của cơ sở đó
        devices = netbox_client.get_devices_by_tenant(tenant_slug=customer.tenant_slug)
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Hệ thống lỗi khi User truy xuất dữ liệu từ NetBox: {str(e)}"
        )

@router.get("/devices/{device_id}")
def get_device_details(device_id: int, admin_user: models.User = Depends(utils.require_admin)):
    """[ADMIN] Lấy thông tin chi tiết thiết bị kèm interfaces"""
    try:
        dev = nb_client.dcim.devices.get(device_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị.")

        interfaces = nb_client.dcim.interfaces.filter(device_id=device_id)
        if_list = [{"id": i.id, "name": i.name, "type": i.type.value if i.type else "Unknown", "enabled": i.enabled, "mac_address": i.mac_address or "N/A"} for i in interfaces]

        return {
            "id": dev.id, "name": dev.name, "serial": dev.serial or "N/A", "device_type": dev.device_type.model if dev.device_type else "Unknown",
            "status": dev.status.value if dev.status else "Unknown", "primary_ip": dev.primary_ip.address if dev.primary_ip else "N/A",
            "interfaces_count": len(if_list), "interfaces": if_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(e)}")