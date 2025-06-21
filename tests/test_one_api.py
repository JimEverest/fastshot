import base64
import time
from openai import OpenAI
import openai

# adam
# key = 'sk-kKC42vieYCFsy7Et037c2c02A9F74b649541E94fDbA978D5' 
# _base_url="https://api.adamchatbot.chat/v1"

# aigcbest
# key =  "sk-SQM4hqeCnzMNbLK554D8BcB80f1643B1AdC6Fb36C9162186"
# _base_url = "https://api2.aigcbest.top/v1"
# _model="gemini-2.0-pro-exp-02-05"

#deepseek - not MM
# key =  "sk-62c6ffa214e74393a5158c1c6fb41e04"
# _base_url = "https://api.deepseek.com"
# _model= "deepseek-reasoner" #"gpt-4o" 

#openrouter
_base_url= "https://openrouter.ai/api/v1"
# key= "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"
key= "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"
_model= "google/gemini-2.0-pro-exp-02-05:free" #"gpt-4o" 

client = OpenAI(
    base_url=_base_url,
    api_key=key
)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

image_path = "oss_browser.png"
base64_image = encode_image(image_path)

while True:
    response = client.chat.completions.create(
        model=_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张图片里有什么?请详细描述。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        temperature=1
    )
    print(response)
    print(response.choices[0].message.content)
    time.sleep(1)





# Deepseek
# Openrouter



