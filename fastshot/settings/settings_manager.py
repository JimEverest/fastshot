import configparser
import os
import shutil
from typing import Dict, Any

class SettingsManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, 'config.ini')
        self.config_reset_path = os.path.join(self.base_dir, '_config_reset.ini')
        self.load_settings()
    
    def load_settings(self):
        """加载配置文件"""
        self.config.read(self.config_path, encoding='utf-8')
    
    def save_settings(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
    
    def reset_settings(self):
        """重置配置到默认值"""
        shutil.copyfile(self.config_reset_path, self.config_path)
        self.load_settings()
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取指定部分的所有配置"""
        if section in self.config:
            return dict(self.config[section])
        return {}
    
    def update_section(self, section: str, settings: Dict[str, Any]):
        """更新指定部分的配置"""
        if section not in self.config:
            self.config[section] = {}
        for key, value in settings.items():
            self.config[section][key] = str(value) 