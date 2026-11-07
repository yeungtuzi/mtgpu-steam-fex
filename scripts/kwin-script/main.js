function exitGameMode() {
    callDBus("org.m1000.GameMode", "/GameMode", "org.m1000.GameMode", "Stop");
}

registerShortcut("M1000ExitGameMode", "退出游戏模式 (M1000)", "Meta+Shift+G", exitGameMode);
