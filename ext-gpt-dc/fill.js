(function() {
    // Chỉ chạy nếu chúng ta đang ở trang Stripe Checkout của ChatGPT hoặc iframe Stripe
    if (window.location.hostname !== "js.stripe.com" && window.location.hostname !== "chatgpt.com") {
        return;
    }

    // Xoá mọi flag cũ nếu có
    if (chrome && chrome.storage && chrome.storage.local) {
        chrome.storage.local.remove('stripe_autofill_done');
    }

    function randomString(length, chars = 'abcdefghijklmnopqrstuvwxyz') {
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }

    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function getRandomName() {
        const firstNames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đinh", "Đoàn", "Lâm", "Trịnh", "Mai", "Đào"];
        const middleNames = ["Văn", "Thị", "Thanh", "Minh", "Hữu", "Đức", "Ngọc", "Gia", "Bảo", "Thu", "Hồng", "Hoàng", "Thành", "Đình", "Quang", "Trọng", "Tuấn", "Lan", "Phương", "Khánh", "Xuân"];
        const lastNames = ["Anh", "Bình", "Châu", "Dương", "Giang", "Hải", "Khang", "Linh", "Nhung", "Phương", "Quân", "Sơn", "Trang", "Vy", "Tuấn", "Long", "Cường", "Hùng", "Tùng", "Khoa", "Kiên", "Hiếu", "Nam", "Phúc", "Tâm", "Hương", "Hà", "Yến", "Thảo", "My", "Nhi", "Đạt", "Huy", "Tiến"];
        const first = firstNames[Math.floor(Math.random() * firstNames.length)];
        const middle = middleNames[Math.floor(Math.random() * middleNames.length)];
        const last = lastNames[Math.floor(Math.random() * lastNames.length)];
        return first + " " + middle + " " + last;
    }

    function getRandomAddress1() {
        const streetNames = [
            "Nguyễn Huệ", "Lê Lợi", "Trần Hưng Đạo", "Hai Bà Trưng", "Đồng Khởi", 
            "Lý Tự Trọng", "Nguyễn Đình Chiểu", "Pasteur", "Lê Duẩn", "Nguyễn Thị Minh Khai", 
            "Điện Biên Phủ", "Cách Mạng Tháng Tám", "Nguyễn Trãi", "Võ Văn Tần", "Trương Định", 
            "Bà Huyện Thanh Quan", "Nguyễn Bỉnh Khiêm", "Lê Thánh Tôn", "Tôn Đức Thắng", "Hàm Nghi", 
            "Võ Thị Sáu", "Nam Kỳ Khởi Nghĩa", "Phan Đăng Lưu", "Bạch Đằng", "Đinh Tiên Hoàng", 
            "Hoàng Hoa Thám", "Quang Trung", "Nguyễn Oanh", "Phạm Văn Đồng", "Mai Chí Thọ",
            "Trần Phú", "Kim Mã", "Cầu Giấy", "Hoàng Diệu", "Phan Đình Phùng", "Xã Đàn"
        ];
        const number = Math.floor(Math.random() * 999) + 1;
        return "Số " + number + " " + streetNames[Math.floor(Math.random() * streetNames.length)];
    }

    function getRandomCity() {
        const cities = [
            "Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ", 
            "Nha Trang", "Huế", "Vũng Tàu", "Biên Hòa", "Đà Lạt", 
            "Buôn Ma Thuột", "Vinh", "Thanh Hóa", "Hạ Long", "Thái Nguyên", 
            "Việt Trì", "Quy Nhơn", "Phan Thiết", "Cà Mau", "Long Xuyên", 
            "Rạch Giá", "Mỹ Tho", "Tân An", "Pleiku", "Bắc Ninh", "Hải Dương"
        ];
        return cities[Math.floor(Math.random() * cities.length)];
    }

    function getRandomZip() {
        const zips = ["100000", "700000", "550000", "180000", "900000", "650000", "530000", "790000", "810000", "670000", "260000", "430000", "400000", "200000", "250000"];
        return zips[Math.floor(Math.random() * zips.length)];
    }

    // Helper: simulate typing like a human to trigger Stripe/React events
    async function simulateTyping(element, text) {
        if (!element) return;
        
        // Focus element
        element.focus();
        
        // Clear existing value
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        
        for (let i = 0; i < text.length; i++) {
            element.value += text[i];
            
            // Dispatch standard events
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            
            // Wait random time between 30ms and 80ms
            await new Promise(r => setTimeout(r, Math.random() * 50 + 30));
        }
        
        // Final blur to trigger validation
        element.blur();
    }

    let isFilling = false;
    async function autoFillForm() {
        if (isFilling) return;
        
        // Tìm các ô nhập liệu
        const nameInput = document.querySelector('input[name="name"], input[autocomplete="name"], input[id*="billingName"], input[data-elements-stable-field-name="billingName"]');
        const address1Input = document.querySelector('input[name="addressLine1"], input[autocomplete="address-line1"], input[id*="billingAddressLine1"], input[name="address1"], input[id*="addressLine1"]');
        
        // Nếu không có ô tên hoặc ô địa chỉ thì có thể frame này không phải là frame nhập liệu
        if (!nameInput && !address1Input) return;

        isFilling = true;
        console.log("[ChatGPT AutoFill] Found inputs, starting autofill sequence (NO AUTO CLICK)...");

        // 1. Nhập Tên
        if (nameInput && !nameInput.value) {
            console.log("Typing Name...");
            await simulateTyping(nameInput, getRandomName());
            await new Promise(r => setTimeout(r, 400));
        }

        // 2. Nhập Địa chỉ 1 từ từ (Stripe thường trigger autocomplete/show fields phụ ở đây)
        if (address1Input && !address1Input.value) {
            console.log("Typing Address Line 1 slowly to trigger dropdown...");
            await simulateTyping(address1Input, getRandomAddress1());
            await new Promise(r => setTimeout(r, 800)); // Đợi Stripe load thêm các ô (City, Zip)
            
            // Tìm lại các input vì DOM có thể đã được update để hiển thị ô ẩn
            const currentCityInput = document.querySelector('input[name="locality"], input[autocomplete="address-level2"], input[name="city"], input[id*="billingLocality"]');
            const currentZipInput = document.querySelector('input[name="postalCode"], input[autocomplete="postal-code"], input[name="zip"], input[name="postal_code"], input[id*="billingPostalCode"]');
            
            // 3. Nhập Thành phố
            if (currentCityInput && !currentCityInput.value) {
                console.log("Typing City...");
                await simulateTyping(currentCityInput, getRandomCity());
                await new Promise(r => setTimeout(r, 300));
            }
            
            // 4. Nhập Zip code
            if (currentZipInput && !currentZipInput.value) {
                console.log("Typing ZIP...");
                await simulateTyping(currentZipInput, getRandomZip());
                await new Promise(r => setTimeout(r, 300));
            }

            // 5. Chọn Tỉnh/Thành phố (State/Province dropdown nếu có)
            const stateSelect = document.querySelector('select[name="administrativeArea"], select[autocomplete*="address-level1"], select[name="state"], select[id*="billingAdministrativeArea"]');
            if (stateSelect && !stateSelect.value) {
                console.log("Selecting State/Province...");
                const options = Array.from(stateSelect.options).filter(opt => opt.value && !opt.disabled);
                if (options.length > 0) {
                    const randomOption = options[Math.floor(Math.random() * options.length)];
                    stateSelect.value = randomOption.value;
                    stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    stateSelect.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        }
        
        console.log("[ChatGPT AutoFill] Autofill completed! Absolutely NO submit or click performed.");
        isFilling = false;
    }

    // Quan sát DOM để chạy khi form xuất hiện
    const observer = new MutationObserver((mutations, obs) => {
        const hasForm = document.querySelector('input[name="name"], input[name="addressLine1"], input[autocomplete="address-line1"], input[id*="billingAddressLine1"]');
        if (hasForm) {
            setTimeout(autoFillForm, 800);
            obs.disconnect(); // Chạy 1 lần rồi ngừng quan sát
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    
    // Thử chạy ngay nếu form đã sẵn sàng
    setTimeout(() => {
        if (document.querySelector('input[name="name"], input[name="addressLine1"], input[autocomplete="address-line1"], input[id*="billingAddressLine1"]')) {
            autoFillForm();
            observer.disconnect();
        }
    }, 1200);

})();
