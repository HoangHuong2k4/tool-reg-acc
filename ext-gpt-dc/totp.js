// =============================================
//  TOTP GENERATOR (RFC 6238 - HMAC-SHA1)
//  Dùng Web Crypto API, không cần thư viện ngoài
// =============================================

async function generateTOTP(secret, timeStep = 30, digits = 6) {
    // Decode Base32 secret thành bytes
    function base32Decode(str) {
        const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
        let bits = 0;
        let value = 0;
        const output = [];
        // Xoá padding và chuyển về uppercase
        str = str.replace(/=+$/, '').toUpperCase();
        for (let i = 0; i < str.length; i++) {
            const idx = alphabet.indexOf(str[i]);
            if (idx === -1) continue;
            value = (value << 5) | idx;
            bits += 5;
            if (bits >= 8) {
                output.push((value >>> (bits - 8)) & 255);
                bits -= 8;
            }
        }
        return new Uint8Array(output);
    }

    // Tính time counter hiện tại
    const epoch = Math.floor(Date.now() / 1000);
    const counter = Math.floor(epoch / timeStep);

    // Chuyển counter sang 8-byte big-endian
    const counterBytes = new Uint8Array(8);
    let tmp = counter;
    for (let i = 7; i >= 0; i--) {
        counterBytes[i] = tmp & 0xff;
        tmp = Math.floor(tmp / 256);
    }

    // Import key và tính HMAC-SHA1
    const keyBytes = base32Decode(secret);
    const cryptoKey = await crypto.subtle.importKey(
        'raw', keyBytes,
        { name: 'HMAC', hash: 'SHA-1' },
        false, ['sign']
    );
    const signature = await crypto.subtle.sign('HMAC', cryptoKey, counterBytes);
    const hmac = new Uint8Array(signature);

    // Dynamic Truncation
    const offset = hmac[hmac.length - 1] & 0x0f;
    const code = (
        ((hmac[offset]     & 0x7f) << 24) |
        ((hmac[offset + 1] & 0xff) << 16) |
        ((hmac[offset + 2] & 0xff) <<  8) |
        ((hmac[offset + 3] & 0xff))
    ) % Math.pow(10, digits);

    return String(code).padStart(digits, '0');
}
