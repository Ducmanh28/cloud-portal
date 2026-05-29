/* ==========================================================================
   SUNCLOUD PORTAL - UTILITY FUNCTIONS
   ========================================================================== */

const utils = {
    /**
     * 1. ĐỊNH DẠNG DỮ LIỆU (FORMATTING)
     */
    
    // Định dạng tiền tệ VNĐ (VD: 1500000 -> 1.500.000 ₫)
    formatCurrency(amount) {
        if (amount === null || amount === undefined) return "0 ₫";
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
    },

    // Định dạng ngày giờ chuẩn Việt Nam (VD: 2026-05-17T15:25:39Z -> 17/05/2026 15:25:39)
    formatDate(dateString, includeTime = true) {
        if (!dateString) return "N/A";
        const date = new Date(dateString);
        const options = { year: 'numeric', month: '2-digit', day: '2-digit' };
        if (includeTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
            options.second = '2-digit';
        }
        return date.toLocaleDateString('vi-VN', options);
    },

    // Định dạng dung lượng RAM (Từ MB sang GB nếu cần)
    formatRAM(mb) {
        if (!mb) return "0 MB";
        if (mb >= 1024 && mb % 1024 === 0) {
            return `${mb / 1024} GB`;
        }
        return `${mb} MB`;
    },

    // Định dạng dung lượng lưu trữ chung (Bytes to KB/MB/GB/TB)
    formatBytes(bytes, decimals = 2) {
        if (!bytes || bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    /**
     * 2. SINH GIAO DIỆN (UI GENERATORS)
     */

    // Sinh thẻ Badge trạng thái tương thích với admin.css
    getStatusBadge(status) {
        if (!status) return `<span class="badge badge-status badge-unknown">Unknown</span>`;
        
        const s = status.toString().toLowerCase();
        let badgeClass = 'badge-unknown';
        let label = status;

        switch(s) {
            case 'active':
            case 'running':
            case 'online':
                badgeClass = 'badge-active';
                label = 'Hoạt động';
                break;
            case 'offline':
            case 'stopped':
            case 'failed':
                badgeClass = 'badge-offline';
                label = 'Đã dừng';
                break;
            case 'suspended':
                badgeClass = 'badge-suspended';
                label = 'Tạm khóa';
                break;
            case 'maintenance':
                badgeClass = 'badge-maintenance';
                label = 'Bảo trì';
                break;
            case 'planned':
            case 'staged':
                badgeClass = 'badge-unknown';
                label = 'Đang triển khai';
                break;
        }

        return `<span class="badge badge-status ${badgeClass}">${label}</span>`;
    },

    /**
     * 3. TƯƠNG TÁC TRÌNH DUYỆT (BROWSER UTILS)
     */

    // Lấy tham số từ URL (VD: param 'id' từ trang chi tiết ?id=5)
    getUrlParam(paramName) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(paramName);
    },

    // Copy văn bản vào Clipboard (Dùng cho IP, Password, MAC)
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            alert("Đã sao chép: " + text); // Có thể thay bằng thư viện Toast sau này
        } catch (err) {
            console.error('Không thể sao chép: ', err);
            alert("Trình duyệt không hỗ trợ sao chép tự động.");
        }
    },

    /**
     * 4. HỖ TRỢ BẢO MẬT & DỮ LIỆU
     */

    // Lấy thông tin user hiện tại từ LocalStorage một cách an toàn
    getCurrentUser() {
        try {
            const userStr = localStorage.getItem('user_info');
            return userStr ? JSON.parse(userStr) : null;
        } catch (e) {
            return null;
        }
    },

    // Kiểm tra quyền Admin
    isAdmin() {
        const user = this.getCurrentUser();
        return user && user.role && user.role.name === "ADMIN";
    }
};