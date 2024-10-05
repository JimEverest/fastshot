# app/config_manager.py
import configparser
import os

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = configparser.ConfigParser()

    def read_config(self):
        self.config.read(self.config_path, encoding='utf-8')

    def get_config(self):
        # 确保读取最新的配置
        self.read_config()
        config_data = {}
        for section in self.config.sections():
            config_data[section] = dict(self.config.items(section))

        return config_data

    def update_config(self, form_data):
        # 收集所有配置项的键
        all_keys = {}
        for section in self.config.sections():
            for option in self.config[section]:
                all_keys[f"{section}.{option}"] = (section, option)

        # 更新配置
        for key_tuple, (section, option) in all_keys.items():
            form_value = form_data.get(key_tuple)

            if self.config[section][option] in ['True', 'False']:
                # 处理布尔值
                if form_value == 'True':
                    self.config[section][option] = 'True'
                else:
                    self.config[section][option] = 'False'
            else:
                if form_value is not None:
                    self.config[section][option] = form_value

        # 保存配置
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
