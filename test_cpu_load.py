import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import time

MODEL_ID = "google/translategemma-12b-it"

def test_cpu_load():
    print("Testing model load on CPU with 8-bit quantization...")
    start = time.time()
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
        )
        
        # Force CPU
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            device_map={"": "cpu"},
            quantization_config=quantization_config,
            trust_remote_code=True
        )
        
        print(f"Model loaded successfully on CPU in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"Error loading on CPU: {e}")
        return False

if __name__ == "__main__":
    test_cpu_load()
