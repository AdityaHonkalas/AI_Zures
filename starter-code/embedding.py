# Embedding model
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()


model =  os.environ.get("MODEL")
gateway_base_url = os.environ.get("GATEWAY_BASE_URL")
gateway_api_key = os.environ.get("GATEWAY_API_KEY")




openai_client = OpenAI(api_key=gateway_api_key, base_url=gateway_base_url)
response = openai_client.embeddings.create(
            input="hi",
            model=model
)

print(response.dict()['data'][0]['embedding'])