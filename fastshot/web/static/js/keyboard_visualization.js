// static/js/keyboard_visualization.js
function visualizeKeyboard(hotkeys) {
    const canvas = document.getElementById('keyboardCanvas');
    const ctx = canvas.getContext('2d');

    // 绘制键盘的函数（简化示例）
    function drawKeyboard() {
        // 绘制键盘背景
        ctx.fillStyle = '#f0f0f0';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 定义键位
        let keys = [
            { key: 'ctrl', x: 50, y: 200, width: 60, height: 60 },
            { key: 'shift', x: 120, y: 200, width: 60, height: 60 },
            { key: 'alt', x: 190, y: 200, width: 60, height: 60 },
            // 更多键位...
        ];

        // 绘制键位
        keys.forEach(k => {
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(k.x, k.y, k.width, k.height);
            ctx.strokeRect(k.x, k.y, k.width, k.height);
            ctx.fillStyle = '#000000';
            ctx.fillText(k.key, k.x + 10, k.y + 35);
        });

        // 根据热键高亮键位
        for (let hotkey in hotkeys) {
            let combination = hotkeys[hotkey].split('+');
            combination.forEach(key => {
                key = key.replace(/<|>/g, '');
                keys.forEach(k => {
                    if (k.key === key.toLowerCase()) {
                        ctx.fillStyle = '#ffcc00';
                        ctx.fillRect(k.x, k.y, k.width, k.height);
                        ctx.strokeRect(k.x, k.y, k.width, k.height);
                        ctx.fillStyle = '#000000';
                        ctx.fillText(k.key, k.x + 10, k.y + 35);
                    }
                });
            });
        }
    }

    drawKeyboard();
}
