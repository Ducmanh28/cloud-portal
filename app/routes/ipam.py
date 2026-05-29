from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

# Import từ thư mục cha
from .. import models, utils
from ..netbox_client import nb_client

router = APIRouter(prefix="/api/v1/ipam", tags=["IP Address Management (IPAM)"])

# ==========================================
# 1. API: QUẢN LÝ ĐỊA CHỈ IP (IP ADDRESSES)
# ==========================================
@router.get("/ip-addresses")
def get_ip_addresses(
    tenant_slug: Optional[str] = None,
    current_user: models.User = Depends(utils.get_current_user)
):
    """
    Lấy danh sách Địa chỉ IP.
    [ADMIN]: Xem tất cả hoặc lọc theo tenant_slug.
    [USER]: Bắt buộc chỉ xem được IP thuộc Tenant của mình.
    """
    try:
        user_role = current_user.role.name if current_user.role else "USER"
        query_params = {}

        if user_role.upper() == "ADMIN":
            if tenant_slug:
                query_params['tenant'] = tenant_slug
        else:
            # Quyền USER: Ép cứng query theo tenant của user hiện tại, bỏ qua request tenant_slug
            if not current_user.customer or not current_user.customer.tenant_slug:
                return {"total": 0, "ip_addresses": []}
            query_params['tenant'] = current_user.customer.tenant_slug

        # Gọi API NetBox
        if query_params:
            ips = nb_client.ipam.ip_addresses.filter(**query_params)
        else:
            ips = nb_client.ipam.ip_addresses.all()

        results = []
        for ip in ips:
            results.append({
                "id": ip.id,
                "address": ip.address,
                "status": ip.status.value if ip.status else "Unknown",
                "tenant": ip.tenant.name if ip.tenant else "None",
                "assigned_object": str(ip.assigned_object) if ip.assigned_object else "Unassigned",
                "dns_name": ip.dns_name or "N/A"
            })
            
        return {"total": len(results), "ip_addresses": results}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 2. API: QUẢN LÝ VLANs
# ==========================================
@router.get("/vlans")
def get_vlans(
    tenant_slug: Optional[str] = None,
    current_user: models.User = Depends(utils.get_current_user)
):
    """
    Lấy danh sách VLANs.
    [ADMIN]: Xem tất cả hoặc lọc theo tenant.
    [USER]: Chỉ xem VLAN được cấp phát cho Tenant của mình.
    """
    try:
        user_role = current_user.role.name if current_user.role else "USER"
        query_params = {}

        if user_role.upper() == "ADMIN":
            if tenant_slug:
                query_params['tenant'] = tenant_slug
        else:
            if not current_user.customer or not current_user.customer.tenant_slug:
                return {"total": 0, "vlans": []}
            query_params['tenant'] = current_user.customer.tenant_slug

        if query_params:
            vlans = nb_client.ipam.vlans.filter(**query_params)
        else:
            vlans = nb_client.ipam.vlans.all()

        results = []
        for vlan in vlans:
            results.append({
                "id": vlan.id,
                "vid": vlan.vid,
                "name": vlan.name,
                "status": vlan.status.value if vlan.status else "Unknown",
                "tenant": vlan.tenant.name if vlan.tenant else "None",
                "site": vlan.site.name if vlan.site else "Global"
            })
            
        return {"total": len(results), "vlans": results}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 3. API: QUẢN LÝ SUBNETS (PREFIXES)
# ==========================================
@router.get("/prefixes")
def get_prefixes(
    tenant_slug: Optional[str] = None,
    admin_user: models.User = Depends(utils.require_admin)
):
    """
    [ADMIN] Lấy danh sách các dải mạng (Prefixes/Subnets).
    Chức năng này tác động đến quy hoạch hạ tầng core, chỉ Admin mới được phép gọi.
    """
    try:
        query_params = {}
        if tenant_slug:
            query_params['tenant'] = tenant_slug

        if query_params:
            prefixes = nb_client.ipam.prefixes.filter(**query_params)
        else:
            prefixes = nb_client.ipam.prefixes.all()

        results = []
        for prefix in prefixes:
            results.append({
                "id": prefix.id,
                "prefix": prefix.prefix,
                "status": prefix.status.value if prefix.status else "Unknown",
                "tenant": prefix.tenant.name if prefix.tenant else "None",
                "site": prefix.site.name if prefix.site else "Global",
                "vlan": f"{prefix.vlan.name} (VID: {prefix.vlan.vid})" if prefix.vlan else "Unassigned",
                "description": prefix.description or ""
            })
            
        return {"total": len(results), "prefixes": results}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(e)}")