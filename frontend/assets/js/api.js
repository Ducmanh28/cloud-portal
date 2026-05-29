/* ==========================================================================
   SUNCLOUD PORTAL - API CLIENT
   ========================================================================== */

// Địa chỉ gốc của Backend (Thay đổi IP theo server thực tế của bạn)
const API_BASE_URL = "http://172.16.66.82:8000/api/v1";

const apiClient = {
    /**
     * Hàm gọi API tổng quát có tích hợp sẵn cấu hình Token và xử lý lỗi
     * @param {string} endpoint - Đường dẫn API (vd: "/iam/users/me")
     * @param {object} options - Các cấu hình thêm cho fetch (method, body...)
     * @returns {Promise<any>} - Dữ liệu JSON trả về từ Backend
     */
    async fetch(endpoint, options = {}) {
        // Lấy token từ LocalStorage
        const token = localStorage.getItem("access_token");
        
        // Thiết lập Header mặc định
        const headers = {
            "Content-Type": "application/json",
            ...(options.headers || {})
        };

        // Nếu có Token, tự động gắn vào Header Authorization (Chuẩn Bearer)
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const config = {
            ...options,
            headers: headers
        };

        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
            
            // Xử lý kịch bản mất quyền hoặc Token hết hạn
            if (response.status === 401) {
                console.warn("Token đã hết hạn hoặc không hợp lệ. Yêu cầu đăng nhập lại.");
                localStorage.removeItem("access_token");
                localStorage.removeItem("user_info");
                
                // Tự động chuyển hướng về trang đăng nhập
                // Sử dụng đường dẫn tuyệt đối hoặc tương đối tùy cấu trúc host
                window.location.href = window.location.pathname.includes('/frontend/') 
                    ? '/frontend/login.html' 
                    : '/login.html';
                
                throw new Error("Phiên đăng nhập đã hết hạn.");
            }

            // Phân tích dữ liệu JSON (Bỏ qua nếu response trả về rỗng - 204 No Content)
            let data = null;
            if (response.status !== 204) {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    data = await response.json();
                }
            }
            
            // Nếu API báo lỗi (Status code >= 400), ném ra lỗi để giao diện bắt (catch)
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