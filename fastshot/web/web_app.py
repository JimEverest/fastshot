# app/app.py
from flask import Flask, render_template, request, redirect, url_for
from .config_manager import ConfigManager
import os
import shutil

app = Flask(__name__)

# 确定 config.ini 和 _config_reset.ini 的路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
CONFIG_RESET_PATH = os.path.join(BASE_DIR, '_config_reset.ini')

# 实例化配置管理器
config_manager = ConfigManager(CONFIG_PATH)

@app.route('/')
def index():
    return redirect(url_for('config'))

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        # 从表单获取数据并更新配置
        form_data = request.form.to_dict()
        config_manager.update_config(form_data)
        return redirect(url_for('config'))
    else:
        # 每次加载页面时，重新读取配置
        config_manager.read_config()
        config_data = config_manager.get_config()
        return render_template('config.html', config_data=config_data)

@app.route('/reset_config')
def reset_config():
    # 将 _config_reset.ini 的内容复制到 config.ini
    shutil.copyfile(CONFIG_RESET_PATH, CONFIG_PATH)
    return redirect(url_for('config'))

@app.route('/dashboard')
def dashboard():
    # 未来实现的功能
    return render_template('dashboard.html')

@app.route('/keyboard')
def keyboard():
    # 渲染 keyboard.html 模板
    return render_template('keyboard.html')

if __name__ == '__main__':
    app.run()
