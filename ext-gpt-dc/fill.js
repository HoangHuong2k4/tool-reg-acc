(function() {
    // Chỉ chạy nếu chúng ta đang ở trang Stripe Checkout của ChatGPT
    if (window.location.hostname !== "js.stripe.com" && window.location.hostname !== "chatgpt.com") {
        return;
    }

    // Nếu ở Top Frame (chatgpt.com): poll chrome.storage để phát hiện fill xong rồi click Subscribe
    if (window.location.hostname === "chatgpt.com") {
        // Xoá flag cũ khi trang mới load
        chrome.storage.local.remove('stripe_autofill_done');

        const pollInterval = setInterval(() => {
            chrome.storage.local.get('stripe_autofill_done', (result) => {
                if (!result.stripe_autofill_done) return;
                clearInterval(pollInterval);
                chrome.storage.local.remove('stripe_autofill_done');
                console.log('[ChatGPT AutoFill] Flag detected! Starting to spam click Subscribe...');
                
                // SPAM click mỗi 1 giây cho đến khi rời trang checkout
                const clickSpammer = setInterval(() => {
                    if (!window.location.href.includes('/checkout')) {
                        clearInterval(clickSpammer);
                        return;
                    }

                    const submitBtn =
                        document.querySelector('button[data-testid="checkout-submit-button"]') ||
                        document.querySelector('button[aria-label="Subscribe"]') ||
                        Array.from(document.querySelectorAll('button[type="submit"]')).find(b => b.textContent.toLowerCase().includes('subscribe') || b.textContent.toLowerCase().includes('tiếp tục') || b.textContent.toLowerCase().includes('claim')) ||
                        document.querySelector('button[type="submit"]');

                    if (submitBtn) {
                        if (!submitBtn.disabled) {
                            console.log('[ChatGPT AutoFill] SPAM Clicking:', submitBtn.textContent.trim());
                            submitBtn.click();
                        } else {
                            console.log('[ChatGPT AutoFill] Button is DISABLED, waiting for Stripe validation...');
                        }
                    } else {
                        console.log('[ChatGPT AutoFill] Subscribe button not found, trying form submit...');
                        const f = document.querySelector('form[id^="_r_"]') || document.querySelector('form');
                        if (f) f.requestSubmit();
                    }
                }, 1000);
            });
        }, 500); // kiểm tra mỗi 500ms

        return; // Dừng ở đây, không chạy logic fill form
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
        const firstNames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi"];
        const middleNames = ["Văn", "Thị", "Thanh", "Minh", "Hữu", "Đức", "Ngọc", "Gia", "Bảo", "Thu"];
        const lastNames = ["Anh", "Bình", "Châu", "Dương", "Giang", "Hải", "Khang", "Linh", "Nhung", "Phương", "Quân", "Sơn", "Trang", "Vy"];
        const first = firstNames[Math.floor(Math.random() * firstNames.length)];
        const middle = middleNames[Math.floor(Math.random() * middleNames.length)];
        const last = lastNames[Math.floor(Math.random() * lastNames.length)];
        return first + " " + middle + " " + last;
    }

    function getRandomAddress1() {
        const streetNames = ["Nguyễn Huệ", "Lê Lợi", "Trần Hưng Đạo", "Hai Bà Trưng", "Đồng Khởi", "Lý Tự Trọng", "Nguyễn Đình Chiểu", "Pasteur", "Lê Duẩn", "Nguyễn Thị Minh Khai"];
        const number = Math.floor(Math.random() * 999) + 1;
        return "Số " + number + " " + streetNames[Math.floor(Math.random() * streetNames.length)];
    }

    function getRandomCity() {
        const cities = ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ", "Nha Trang", "Huế", "Vũng Tàu", "Biên Hòa", "Đà Lạt"];
        return cities[Math.floor(Math.random() * cities.length)];
    }

    function getRandomZip() {
        // Zip code VN thường là 5 hoặc 6 số (VD: 100000, 700000)
        const zips = ["100000", "700000", "550000", "180000", "900000", "650000", "530000", "790000", "810000", "670000"];
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

    async function autoFillForm() {
        // Tìm các ô nhập liệu
        const nameInput = document.querySelector('input[name="name"], input[autocomplete="name"]');
        const address1Input = document.querySelector('input[name="addressLine1"], input[autocomplete="address-line1"], input[autocomplete="address-line1"]');
        const cityInput = document.querySelector('input[name="locality"], input[autocomplete="address-level2"], input[name="city"]');
        const zipInput = document.querySelector('input[name="postalCode"], input[autocomplete="postal-code"], input[name="zip"]');
        
        // Nếu không có ô tên hoặc ô địa chỉ thì có thể frame này không phải là frame nhập liệu, bỏ qua
        if (!nameInput && !address1Input) return;

        console.log("[ChatGPT AutoFill] Found inputs, starting autofill sequence...");

        // 1. Nhập Tên
        if (nameInput && !nameInput.value) {
            console.log("Typing Name...");
            await simulateTyping(nameInput, getRandomName());
            await new Promise(r => setTimeout(r, 500)); // Nghỉ 0.5s sau khi nhập tên
        }

        // 2. Nhập Địa chỉ 1 từ từ (Stripe thường trigger autocomplete/show fields phụ ở đây)
        if (address1Input && !address1Input.value) {
            console.log("Typing Address Line 1 slowly to trigger dropdown...");
            await simulateTyping(address1Input, getRandomAddress1());
            await new Promise(r => setTimeout(r, 1000)); // Đợi 1s cho Stripe load thêm các ô (City, Zip, Address 2)
            
            // Tìm lại các input vì DOM có thể đã được update để hiển thị ô ẩn
            const currentCityInput = document.querySelector('input[name="locality"], input[autocomplete="address-level2"], input[name="city"]');
            const currentZipInput = document.querySelector('input[name="postalCode"], input[autocomplete="postal-code"], input[name="zip"]');
            
            // 3. Nhập Thành phố
            if (currentCityInput && !currentCityInput.value) {
                console.log("Typing City...");
                await simulateTyping(currentCityInput, getRandomCity());
                await new Promise(r => setTimeout(r, 400));
            }
            
            // 4. Nhập Zip code
            if (currentZipInput && !currentZipInput.value) {
                console.log("Typing ZIP...");
                await simulateTyping(currentZipInput, getRandomZip());
                await new Promise(r => setTimeout(r, 400));
            }

            // 5. Chọn Tỉnh/Thành phố (State/Province dropdown)
            const stateSelect = document.querySelector('select[name="administrativeArea"], select[autocomplete*="address-level1"], select[name="state"]');
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
        
        console.log("[ChatGPT AutoFill] Autofill completed! Setting storage flag...");
        // Dùng chrome.storage thay postMessage để tránh cross-origin bị chặn
        chrome.storage.local.set({ stripe_autofill_done: true });
    }

    // Quan sát DOM để chạy khi form xuất hiện
    const observer = new MutationObserver((mutations, obs) => {
        const hasForm = document.querySelector('input[name="name"], input[name="addressLine1"]');
        if (hasForm) {
            // Đợi thêm 1 chút cho JS của Stripe attach event listeners
            setTimeout(autoFillForm, 1000);
            obs.disconnect(); // Chạy 1 lần rồi ngừng quan sát
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    
    // Thử chạy ngay lập tức nếu form đã sẵn sàng
    setTimeout(() => {
        if (document.querySelector('input[name="name"], input[name="addressLine1"]')) {
            autoFillForm();
            observer.disconnect();
        }
    }, 1500);

})();
