// =========================================================================
// CapCut Auto Login - Ultra-Simple Popup Script
// =========================================================================

document.addEventListener("DOMContentLoaded", async () => {
  const inp = document.getElementById("inp");
  const btn = document.getElementById("btn");
  const status = document.getElementById("status");

  // Load last entered input
  const data = await chrome.storage.local.get(["lastInput"]);
  if (data.lastInput) {
    inp.value = data.lastInput;
    status.textContent = `Sẵn sàng: ${data.lastInput.split(/\t|\||\s+/)[0]}`;
  }

  function handleInput() {
    const val = inp.value.trim();
    if (val) {
      chrome.storage.local.set({ lastInput: val });
      const email = val.split(/\t|\||\s+/)[0];
      status.textContent = `Nhận diện: ${email}`;
      status.style.color = "#00f0fe";
    } else {
      status.textContent = "Dán acc rồi bấm Đăng nhập";
      status.style.color = "#94a3b8";
    }
  }

  inp.addEventListener("input", handleInput);

  async function triggerLogin() {
    const val = inp.value.trim();
    if (!val) {
      status.textContent = "❌ Vui lòng nhập email|pass hoặc email	pass!";
      status.style.color = "#ef4444";
      inp.focus();
      return;
    }

    await chrome.storage.local.set({ lastInput: val });
    status.textContent = "🚀 Đang mở CapCut...";
    status.style.color = "#10b981";

    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (activeTab && activeTab.url && activeTab.url.includes("capcut.com")) {
      try {
        await chrome.tabs.sendMessage(activeTab.id, { type: "TRIGGER_LOGIN" });
        setTimeout(() => window.close(), 300);
        return;
      } catch (err) {}
    }

    chrome.runtime.sendMessage({ type: "OPEN_CAPCUT_LOGIN" }, () => {
      setTimeout(() => window.close(), 300);
    });
  }

  btn.addEventListener("click", triggerLogin);
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      triggerLogin();
    }
  });
});
