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

            // In log ra Console để bạn dễ dàng kiểm tra cấu hình thực tế của Response
            console.log("Khởi chạy đăng nhập thành công. Phản hồi hệ thống:", response);

            // 1. Lưu Access Token vào hệ thống lưu trữ của trình duyệt
            localStorage.setItem("access_token", response.access_token);

            let userRole = "user";
            let userPayload = { username: usernameInput, role: { name: "USER" } };

            // Khối xử lý phòng vệ dữ liệu bóc tách Role
            if (response.user) {
                // Kịch bản A: Nếu Backend có đính kèm cấu trúc Object User riêng biệt
                userPayload = response.user;
                userRole = userPayload.role ? userPayload.role.name.toLowerCase() : "user";
            } else if (response.access_token) {
                // Kịch bản B: Nếu Backend trả về Token thuần, thực hiện bóc tách JWT Payload
                try {
                    const payloadBase64 = response.access_token.split('.')[1];
                    const decodedPayload = JSON.parse(atob(payloadBase64));
                    
                    // Lấy role từ JWT (nếu Backend có nhét trường role/roles vào token payload)
                    if (decodedPayload.role) {
                        userRole = decodedPayload.role.toLowerCase();
                    } else if (usernameInput === "admin") {
                        // Cơ chế Fallback an toàn nếu hệ thống Lab chưa cấu hình map role vào Token
                        userRole = "admin";
                    }

                    userPayload = {
                        username: decodedPayload.sub || usernameInput,
                        role: { name: userRole.toUpperCase() }
                    };
                } catch (jwtError) {
                    console.error("Lỗi phân rã cấu trúc chuỗi token mã hóa:", jwtError);
                }
            }

            // 2. Lưu thông tin tài khoản đã chuẩn hóa vào LocalStorage để hiển thị lên thanh Navbar
            localStorage.setItem("user", JSON.stringify(userPayload));

            // 3. Phân luồng điều hướng dựa trên kết quả phân tích quyền hạn
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

