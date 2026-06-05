from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, utils
from ..database import get_db
from ..netbox_client import nb_client

router = APIRouter(prefix="/api/v1/dcim", tags=["DCIM (Physical Infrastructure)"])


def _status(obj, default="Unknown"):
    value = getattr(obj, "status", None)
    return getattr(value, "value", default) if value else default


def _name(obj, field, default="N/A"):
    value = getattr(obj, field, None)
    return getattr(value, "name", default) if value else default


def _device_role_name(device):
    role = getattr(device, "role", None) or getattr(device, "device_role", None)
    return getattr(role, "name", "Unknown") if role else "Unknown"


def _device_type_name(device):
    device_type = getattr(device, "device_type", None)
    return getattr(device_type, "model", "Unknown") if device_type else "Unknown"


def _primary_ip(device):
    ip = getattr(device, "primary_ip", None)
    return getattr(ip, "address", "N/A") if ip else "N/A"


def _customer_tenant_slug(db: Session, current_user: models.User):
    if not current_user.customer_id:
        return None
    customer = db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).first()
    if not customer:
        return None
    return customer.tenant_slug


def _map_device(device):
    return {
        "id": device.id,
        "name": device.name,
        "device_type": _device_type_name(device),
        "device_role": _device_role_name(device),
        "tenant": _name(device, "tenant", "None"),
        "site": _name(device, "site", "Unknown"),
        "rack": _name(device, "rack", "N/A"),
        "position": getattr(device, "position", None),
        "primary_ip": _primary_ip(device),
        "status": _status(device),
    }


@router.get("/sites")
def get_all_sites(admin_user: models.User = Depends(utils.require_admin)):
    try:
        sites = nb_client.dcim.sites.all()
        results = []
        for site in sites:
            results.append({
                "id": site.id,
                "name": site.name,
                "slug": site.slug,
                "status": _status(site),
                "facility": getattr(site, "facility", None) or "N/A",
            })
        return {"total": len(results), "sites": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.get("/racks")
def get_all_racks(site_slug: str = None, admin_user: models.User = Depends(utils.require_admin)):
    try:
        racks = nb_client.dcim.racks.filter(site=site_slug) if site_slug else nb_client.dcim.racks.all()
        results = []
        for rack in racks:
            results.append({
                "id": rack.id,
                "name": rack.name,
                "site": _name(rack, "site"),
                "status": _status(rack),
                "role": _name(rack, "role"),
                "u_height": getattr(rack, "u_height", None),
            })
        return {"total": len(results), "racks": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.get("/devices")
def get_devices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    role = current_user.role.name.upper() if current_user.role else "USER"
    query_params = {}

    if role != "ADMIN":
        tenant_slug = _customer_tenant_slug(db, current_user)
        if not tenant_slug:
            return {"devices": []}
        query_params["tenant"] = tenant_slug

    try:
        devices = nb_client.dcim.devices.filter(**query_params) if query_params else nb_client.dcim.devices.all()
        return {"devices": [_map_device(device) for device in devices]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Hệ thống lỗi khi truy xuất dữ liệu từ NetBox: {str(exc)}")


@router.get("/devices/{device_id}")
def get_device_details(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    try:
        device = nb_client.dcim.devices.get(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị.")

        role = current_user.role.name.upper() if current_user.role else "USER"
        if role != "ADMIN":
            tenant_slug = _customer_tenant_slug(db, current_user)
            device_tenant = getattr(getattr(device, "tenant", None), "slug", None)
            if not tenant_slug or device_tenant != tenant_slug:
                raise HTTPException(status_code=403, detail="Không có quyền xem thiết bị này.")

        interfaces = nb_client.dcim.interfaces.filter(device_id=device_id)
        interface_list = []
        for interface in interfaces:
            interface_type = getattr(interface, "type", None)
            interface_list.append({
                "id": interface.id,
                "name": interface.name,
                "type": getattr(interface_type, "value", "Unknown") if interface_type else "Unknown",
                "enabled": getattr(interface, "enabled", False),
                "mac_address": getattr(interface, "mac_address", None) or "N/A",
            })

        result = _map_device(device)
        result.update({
            "serial": getattr(device, "serial", None) or "N/A",
            "interfaces_count": len(interface_list),
            "interfaces": interface_list,
        })
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(exc)}")
