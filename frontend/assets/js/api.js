/* ==========================================================================
   SUNCLOUD PORTAL - API CLIENT
   ========================================================================== */

// Địa chỉ gốc của Backend (Thay đổi IP theo server thực tế của bạn)
const API_BASE_URL = window.API_BASE_URL || "http://172.16.66.82:8000/api/v1";

const apiClient = {
    /**
     * Hàm gọi API tổng quát có tích hợp sẵn cấu hình Token và xử lý lỗi
     * @param {string} endpoint - Đường dẫn API (vd: "/iam/users/me")
     * @param {object} options - Các cấu hình thêm cho fetch (method, body...)
     * @returns {Promise<any>} - Dữ liệu JSON trả về từ Backend
     */
    async fetch(endpoint, options = {}) {
        const token = localStorage.getItem("access_token");
        
        const headers = {
            "Content-Type": "application/json",
            ...(options.headers || {})
        };

        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const config = {
            ...options,
            headers: headers
        };

        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
            
            if (response.status === 401) {
                console.warn("Token đã hết hạn hoặc không hợp lệ. Yêu cầu đăng nhập lại.");
                localStorage.removeItem("access_token");
                localStorage.removeItem("user");
                localStorage.removeItem("user_info");
                
                window.location.href = window.location.pathname.includes('/frontend/') 
                    ? '/frontend/login.html' 
                    : '/login.html';
                
                throw new Error("Phiên đăng nhập đã hết hạn.");
            }

            let data = null;
            if (response.status !== 204) {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    data = await response.json();
                }
            }
            
            if (!response.ok) {
                const errorMsg = data && data.detail ? data.detail : `Lỗi hệ thống: ${response.status} ${response.statusText}`;
                throw new Error(errorMsg);
            }

            return data;
        } catch (error) {
            console.error(`[API Call Failed] ${endpoint}:`, error);
            throw error;
        }
    }
};
