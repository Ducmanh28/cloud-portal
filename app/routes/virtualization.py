from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Import từ thư mục cha
from ..database import get_db
from .. import models, utils
from ..netbox_client import nb_client

router = APIRouter(prefix="/api/v1/virtualization", tags=["Virtualization (VMs & Clusters)"])


class PowerActionRequest(BaseModel):
    action: str

# ==========================================
# 1. API: QUẢN LÝ CỤM ẢO HÓA (CLUSTERS)
# ==========================================
@router.get("/clusters")
def get_clusters(
    current_user: models.User = Depends(utils.get_current_user), 
    db: Session = Depends(get_db)
):
    """
    [ADMIN] Lấy danh sách các cụm máy chủ ảo hóa.
    Chỉ Quản trị viên hệ thống mới được phép xem tài nguyên hạ tầng lõi này.
    """
    user_role = current_user.role.name.upper() if current_user.role else "USER"
    if user_role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập tài nguyên này.")

    try:
        clusters = nb_client.virtualization.clusters.all()
        results = []
        for cluster in clusters:
            results.append({
                "id": cluster.id,
                "name": cluster.name,
                "type": cluster.type.name if getattr(cluster, 'type', None) else "Unknown",
                "status": cluster.status.value if getattr(cluster, 'status', None) else "Unknown",
                "site": cluster.site.name if getattr(cluster, 'site', None) else "N/A",
                "tenant": cluster.tenant.name if getattr(cluster, 'tenant', None) else "Internal"
            })
        return {"total": len(results), "clusters": results}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 2. API: QUẢN LÝ MÁY ẢO (VIRTUAL MACHINES)
# ==========================================
@router.get("/vms")
def get_vms(
    tenant_slug: Optional[str] = None,
    current_user: models.User = Depends(utils.get_current_user)
):
    """
    Lấy danh sách các máy ảo (VPS/Nodes).
    [ADMIN]: Lấy toàn bộ máy ảo trên hệ thống, hoặc lọc theo tenant_slug.
    [USER]: Chỉ lấy các máy ảo thuộc về đúng công ty của họ.
    """
    try:
        user_role = current_user.role.name.upper() if current_user.role else "USER"
        query_params = {}

        if user_role == "ADMIN":
            if tenant_slug:
                query_params['tenant'] = tenant_slug
        else:
            if not current_user.customer or not current_user.customer.tenant_slug:
                return {"total": 0, "vms": []}
            query_params['tenant'] = current_user.customer.tenant_slug

        if query_params:
            vms = nb_client.virtualization.virtual_machines.filter(**query_params)
        else:
            vms = nb_client.virtualization.virtual_machines.all()

        results = []
        for vm in vms:
            results.append({
                "id": vm.id,
                "name": vm.name,
                "status": vm.status.value if getattr(vm, 'status', None) else "Unknown",
                "cluster": vm.cluster.name if getattr(vm, 'cluster', None) else "Unassigned",
                "tenant": vm.tenant.name if getattr(vm, 'tenant', None) else "None",
                "vcpus": int(vm.vcpus) if getattr(vm, 'vcpus', None) else 0,
                "memory_mb": int(vm.memory) if getattr(vm, 'memory', None) else 0,
                "disk_gb": int(vm.disk) if getattr(vm, 'disk', None) else 0,
                "primary_ip": vm.primary_ip.address if getattr(vm, 'primary_ip', None) else "N/A"
            })
            
        return {"total": len(results), "vms": results}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 3. API: CHI TIẾT MÁY ẢO
# ==========================================
@router.get("/vms/{vm_id}")
def get_vm_details(
    vm_id: int, 
    current_user: models.User = Depends(utils.get_current_user)
):
    """Lấy thông tin chi tiết cấu hình của một máy ảo cụ thể"""
    try:
        vm = nb_client.virtualization.virtual_machines.get(vm_id)
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy máy ảo.")

        user_role = current_user.role.name.upper() if current_user.role else "USER"
        
        if user_role != "ADMIN":
            my_tenant = current_user.customer.tenant_slug if current_user.customer else None
            if not my_tenant or getattr(vm, 'tenant', None) is None or vm.tenant.slug != my_tenant:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Bạn không có quyền truy cập máy ảo của tổ chức khác."
                )

        interfaces = nb_client.virtualization.interfaces.filter(virtual_machine_id=vm_id)
        if_list = [{
            "id": i.id,
            "name": i.name,
            "mac_address": i.mac_address or "N/A",
            "enabled": i.enabled
        } for i in interfaces]

        return {
            "id": vm.id,
            "name": vm.name,
            "status": vm.status.value if getattr(vm, 'status', None) else "Unknown",
            "cluster": vm.cluster.name if getattr(vm, 'cluster', None) else "Unassigned",
            "tenant": vm.tenant.name if getattr(vm, 'tenant', None) else "None",
            "vcpus": int(vm.vcpus) if getattr(vm, 'vcpus', None) else 0,
            "memory_mb": int(vm.memory) if getattr(vm, 'memory', None) else 0,
            "disk_gb": int(vm.disk) if getattr(vm, 'disk', None) else 0,
            "primary_ip": vm.primary_ip.address if getattr(vm, 'primary_ip', None) else "N/A",
            "comments": vm.comments or "",
            "interfaces_count": len(if_list),
            "interfaces": if_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(e)}")

# ==========================================
# 4. API: THỰC THI LỆNH MÁY ẢO (POWER ACTIONS)
# ==========================================
@router.post("/vms/{vm_id}/power")
def power_action_vm(
    vm_id: int, 
    payload: PowerActionRequest, 
    current_user: models.User = Depends(utils.get_current_user)
):
    """Gửi lệnh điều khiển nguồn tới máy ảo."""
    action = payload.action.lower().strip()
    valid_actions = ["start", "stop", "restart", "shutdown"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Hành động không hợp lệ. Chỉ chấp nhận: {valid_actions}")

    try:
        vm = nb_client.virtualization.virtual_machines.get(vm_id)
        if not vm:
            raise HTTPException(status_code=404, detail="Không tìm thấy máy ảo.")

        user_role = current_user.role.name.upper() if current_user.role else "USER"
        
        if user_role != "ADMIN":
            my_tenant = current_user.customer.tenant_slug if current_user.customer else None
            if not my_tenant or getattr(vm, 'tenant', None) is None or vm.tenant.slug != my_tenant:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Không có quyền thao tác trên máy ảo này."
                )
        
        return {
            "status": "success",
            "message": f"Đã ghi nhận lệnh '{action.upper()}' cho máy ảo '{vm.name}'.",
            "vm_id": vm_id,
            "action": action
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
