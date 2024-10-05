// static/js/hotkey_capture.js

function captureHotkey(inputId) {
    let inputElement = document.getElementById(inputId);
    inputElement.value = '';
    inputElement.focus();
    let keys = [];

    const keyMap = {
        'arrowdown': '<down>',
        'arrowleft': '<left>',
        'arrowright': '<right>',
        'arrowup': '<up>',
        'control': '<ctrl>',
        'meta': '<cmd>',
        'alt': '<alt>',
        'escape': '<esc>',
        'process': '`',
        'tab': '<tab>',
        'capslock': '<capslock>',
        'backspace': '<backspace>',
        'enter': '<enter>'
    };

    function keydownHandler(event) {
        event.preventDefault();
        let key = event.key.toLowerCase();

        // 映射按键名称
        if (key in keyMap) {
            key = keyMap[key];
        } else if (key.length === 1) {
            // 保留单字符按键
        } else {
            // 将其他按键名称包裹在<>
            key = `<${key}>`;
        }

        if (!keys.includes(key)) {
            keys.push(key);
        }

        inputElement.value = keys.join('+');
    }

    function keyupHandler(event) {
        document.removeEventListener('keydown', keydownHandler);
        document.removeEventListener('keyup', keyupHandler);
    }

    document.addEventListener('keydown', keydownHandler);
    document.addEventListener('keyup', keyupHandler);
}
