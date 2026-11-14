// =========================================================================
// Grok Auto Link Opener - Content Script (content.js)
// CHỈ MỞ LINK REFERRAL - KHÔNG TỰ ĐỘNG CLICK NÚT TRÁNH LỖI THANH TOÁN
// =========================================================================

(() => {
  // Chỉ hiển thị thông báo nhẹ góc màn hình để người dùng biết link đã được mở
  function showBanner(text) {
    try {
      let bannerEl = document.getElementById("grok-auto-opener-banner");
      if (!bannerEl) {
        bannerEl = document.createElement("div");
        bannerEl.id = "grok-auto-opener-banner";
        Object.assign(bannerEl.style, {
          position: "fixed",
          top: "16px",
          right: "16px",
          zIndex: "2147483647",
          padding: "10px 16px",
          borderRadius: "8px",
          fontSize: "13px",
          fontWeight: "600",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          background: "#1e293b",
          color: "#38bdf8",
          border: "1px solid #38bdf8",
          transition: "all 0.3s ease",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          maxWidth: "380px",
          lineHeight: "1.4"
        });
        document.body.appendChild(bannerEl);
      }

      bannerEl.innerHTML = text;
      bannerEl.style.opacity = "1";
      bannerEl.style.transform = "translateY(0)";

      setTimeout(() => {
        if (bannerEl) {
          bannerEl.style.opacity = "0";
          bannerEl.style.transform = "translateY(-10px)";
        }
      }, 5000);
    } catch {}
  }

  // Khi vào trang referral, chỉ hiển thị thông báo và để người dùng tự thao tác
  const url = window.location.href;
  if (url.includes("/refer") || url.includes("code=")) {
    showBanner(`🚀 <b>Grok Auto Opener</b>: Đã mở link ưu đãi. Vui lòng bấm nhận và thanh toán thủ công.`);
  }
})();
