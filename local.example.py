from pathlib import Path
# 此文件仅在本机使用。API key不发给浏览器。
OPENAI_API_KEY = ""
MODEL = "gpt-4.1"
BASE_URL = "https://api.openai.com/v1"
LOG_ENABLED = True
API_TIMEOUT = 180
API_RETRIES = 4
ID_RETRIES = 1
BATCH_CHARACTERS = 6000
MAX_BATCH_ITEMS = 20
MAX_OUTPUT_TOKENS = 12000
TRANSLATION_WORKERS = 3
TARGET_LANGUAGE = "简体中文"
STORY_ONLY = True
MIN_STORY_CHARACTERS = 300
MIN_PLAIN_TEXT_CHARACTERS = 600
MIN_JAPANESE_RATIO = 0.15
OVERRIDES_ROOT = str(Path(__file__).resolve().parent / "Overrides")
OVERRIDE_PATHS = {}
GLOSSARY_FILE = "glossary.json"

# 本地服务与油猴脚本填写同一随机字符串（至少32字符）。
LOCAL_SERVICE_TOKEN = ""
