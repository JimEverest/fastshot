# fastshot/plugin_ask.py

import time
import random

class PluginAsk:
    def __init__(self):
        pass

    def ask(self, question, image_path):
        # 模拟处理时间
        time.sleep(2)
        # 生成随机答案
        answers = [
            "This is a sample answer.",
            "Here is the information you requested.",
            "I'm sorry, but I can't provide that information.",
            "Please provide more details."
        ]
        return random.choice(answers)
