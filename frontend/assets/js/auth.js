/* ========================================================================== 
   SUNCLOUD PORTAL - AUTHENTICATION & ROUTING LOGIC
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("loginForm");
    if (!loginForm) return;

    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const usernameInput = document.getElementById("username").value;
        const passwordInput = document.getElementById("password").value;
        const alertMsg = document.getElementById("alert-msg");
        const loginBtn = document.getElementById("loginBtn");

        // Ẩn thông báo cũ và đổi trạng thái nút
        alertMsg.classList.add("d-none");
        loginBtn.disabled = true;
        loginBtn.innerText = "Đang xác thực...";

        try {
            // Đóng gói dữ liệu dạng Form Data chuẩn OAuth2
            const formData = new URLSearchParams();
            formData.append("username", usernameInput);
            formData.append("password", passwordInput);

            // Gọi API Đăng nhập sang Backend FastAPI
            const response = await apiClient.fetch("/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: formData
            });

            // 1. Lưu Access Token vào hệ thống lưu trữ của trình duyệt
            localStorage.setItem("access_token", response.access_token);

            // 2. Lấy role thật từ backend, không tự suy đoán admin theo username.
            const userPayload = response.user || await apiClient.fetch("/iam/users/me");
            const userRole = userPayload.role ? userPayload.role.name.toLowerCase() : "user";

            localStorage.setItem("user", JSON.stringify(userPayload));
            localStorage.setItem("user_info", JSON.stringify(userPayload));

            // 3. Phân luồng điều hướng dựa trên kết quả phân quyền từ backend
            if (userRole === "admin") {
                window.location.href = "admin/dashboard.html";
            } else {
                window.location.href = "user/dashboard.html";
            }

        } catch (error) {
            alertMsg.className = "alert alert-danger";
            alertMsg.textContent = error.message || "Tên đăng nhập hoặc mật khẩu không chính xác.";
            alertMsg.classList.remove("d-none");
            
            loginBtn.disabled = false;
            loginBtn.innerText = "Đăng Nhập";
        }
    });
});

// Hàm hỗ trợ đăng xuất dùng chung cho toàn hệ thống Portal
window.logout = function() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    localStorage.removeItem("user_info");
    // Di chuyển về trang login gốc tùy thuộc vị trí file đang đứng
    if (window.location.pathname.includes("/user/") || window.location.pathname.includes("/admin/")) {
        window.location.href = "../login.html";
    } else {
        window.location.href = "login.html";
    }
};

/**
 * Lấy thông tin User hiện tại và phân luồng (Admin đi đường Admin, User đi đường User)
 */
async function routeUserToCorrectDashboard() {
    try {
        // Sử dụng apiClient (đã tự động gắn Token) để gọi API
        const userProfile = await apiClient.fetch("/iam/users/me");
        
        // Lưu thông tin user để hiển thị lên Header/Navbar sau này
        localStorage.setItem("user", JSON.stringify(userProfile));
        localStorage.setItem("user_info", JSON.stringify(userProfile));

        // Xác định đường dẫn gốc. Vì bạn chạy Python http.server trong thư mục frontend, 
        // gốc của trang web (/) chính là thư mục frontend.
        const basePath = window.location.pathname.includes('/frontend/') ? '/frontend/' : '/';

        // Phân luồng dựa trên Role
        if (userProfile.role && userProfile.role.name === "ADMIN") {
            window.location.href = basePath + "admin/dashboard.html";
        } else {
            window.location.href = basePath + "user/dashboard.html";
        }
    } catch (error) {
        console.error("Lỗi xác thực phân quyền:", error);
        localStorage.removeItem("access_token");
        localStorage.removeItem("user");
        localStorage.removeItem("user_info");
        
        const alertMsg = document.getElementById("alert-msg");
        if (alertMsg) {
            alertMsg.className = "alert alert-danger";
            alertMsg.textContent = "Không thể lấy thông tin phân quyền hoặc tài khoản bị khóa.";
            alertMsg.classList.remove("d-none");
        }
    }
}

/**
 * Kiểm tra Session hiện tại (Dành cho trang login để tránh bắt người dùng đăng nhập lại)
 */
async function checkExistingSession() {
    const token = localStorage.getItem("access_token");
    if (token) {
        // Nếu có token, thử lấy thông tin và chuyển hướng thẳng vào bên trong
        await routeUserToCorrectDashboard();
    }
}
