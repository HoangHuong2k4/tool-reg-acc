function playMomoSound() {
    try {
        const audio = new Audio('/static/nhac_chuong_pokemon_black_and_white_tiktok-www_tiengdong_com.mp3');
        audio.play();
    } catch(e) {
        console.log("Audio not supported");
    }
}
