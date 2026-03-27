"""
Gemma Translation Service

Provides translation using google/translategemma-12b-it model with:
- 4-bit NF4 quantization via bitsandbytes (~8GB RAM for 12B model)
- AMD Barcelo APU / CPU inference support
- Singleton pattern for efficient model reuse
"""

import os
import time
from typing import Optional, Tuple

MODEL_ID = "google/translategemma-12b-it"

# Language code to name mapping
LANG_MAP = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ru": "Russian",
    "ko": "Korean",
    "hi": "Hindi",
    "ar": "Arabic",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "el": "Greek",
    "he": "Hebrew",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "uk": "Ukrainian",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
}


def detect_device() -> Tuple[str, bool]:
    """
    Detect available compute device.
    For AMD APUs (integrated GPU like Barcelo), we use CPU with 4-bit quantization
    since the iGPU shares system RAM and has ROCm limitations.
    
    Set FORCE_CPU=1 environment variable to override GPU detection.
    
    Returns:
        Tuple of (device_type, use_quantization)
    """
    # Allow explicit CPU override via environment variable
    if os.environ.get('FORCE_CPU', '0') == '1':
        print("FORCE_CPU=1 detected, using CPU with 4-bit quantization")
        return 'cpu', True

    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0).lower()
            # Check if this is an integrated AMD APU (Barcelo, Renoir, Cezanne, etc.)
            apu_names = ['barcelo', 'renoir', 'cezanne', 'rembrandt', 'phoenix']
            is_apu = any(apu in device_name for apu in apu_names)
            if is_apu:
                print(f"Detected AMD APU (integrated GPU): {device_name}")
                print("Using CPU with 4-bit quantization for best APU compatibility")
                return 'cpu', True  # use CPU but still quantize
            elif 'amd' in device_name or 'radeon' in device_name:
                print(f"Detected AMD dGPU: {device_name}")
                return 'rocm', True
            else:
                print(f"Detected NVIDIA GPU: {device_name}")
                return 'cuda', True
        
        print("No GPU detected, using CPU with 4-bit quantization")
        return 'cpu', True  # still use 4-bit to fit in RAM
    except ImportError:
        print("Torch not available, using CPU (Mock)")
        return 'cpu', False


class GemmaService:
    """Singleton service for Gemma translation model."""
    
    _instance = None
    _model = None
    _tokenizer = None
    _device = None
    _use_quantization = False
    _load_time_seconds = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GemmaService, cls).__new__(cls)
        return cls._instance
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None
    
    @property
    def device_info(self) -> dict:
        """Get information about the current device."""
        return {
            'device': self._device,
            'quantized': self._use_quantization,
            'model_id': MODEL_ID,
            'loaded': self.is_loaded,
            'load_time_seconds': self._load_time_seconds
        }
    
    def initialize(self, force_cpu: bool = False) -> None:
        """
        Load the model and tokenizer.
        
        Args:
            force_cpu: If True, skip GPU detection and use CPU
        """
        if self._model is not None:
            return
        
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            print("AI libraries not found. Local translation unavailable.")
            raise ImportError("Please install transformers and torch to use local translation.")

        start_time = time.time()
        
        # Detect device
        if force_cpu:
            self._device = 'cpu'
            self._use_quantization = False
        else:
            self._device, self._use_quantization = detect_device()
        
        print(f"Loading model {MODEL_ID}...")
        print(f"Device: {self._device}, Quantization: {self._use_quantization}")
        
        try:
            from transformers import BitsAndBytesConfig
            self._tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
            
            if self._use_quantization:
                # 4-bit NF4 quantization: ~8GB RAM for 12B model (vs ~24GB fp16)
                # This works on CPU and is compatible with AMD APUs
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
                # For CPU inference, device_map must be 'cpu'
                device_map = "auto" if self._device != 'cpu' else {"":"cpu"}
                self._model = AutoModelForCausalLM.from_pretrained(
                    MODEL_ID,
                    device_map=device_map,
                    quantization_config=quantization_config,
                    trust_remote_code=True
                )
            else:
                # No quantization - use float32 on CPU
                self._model = AutoModelForCausalLM.from_pretrained(
                    MODEL_ID,
                    torch_dtype=torch.float32,
                    low_cpu_mem_usage=True,
                    trust_remote_code=True
                )
            
            self._load_time_seconds = time.time() - start_time
            print(f"Model loaded successfully in {self._load_time_seconds:.1f}s")
            
        except Exception as e:
            print(f"Error loading model: {e}")
            raise e
    
    def translate(self, text: str, source_lang: str = "en", target_lang: str = "es") -> Tuple[str, int]:
        """
        Translate text to the target language using TranslateGemma's structured format.
        
        Args:
            text: Source text to translate
            source_lang: ISO language code of the source (e.g., 'en')
            target_lang: ISO language code of the target (e.g., 'es')
        
        Returns:
            Tuple of (translated_text, translation_time_ms)
        """
        if not text:
            return "", 0
        
        if self._model is None:
            self.initialize()
        
        start_time = time.time()
        
        # TranslateGemma requires a specific structured content format:
        # Each message must have content as a list with exactly one mapping dict
        messages = [
            {
                "role": "user",
                "content": [{
                    "type": "text",
                    "source_lang_code": source_lang.lower(),
                    "target_lang_code": target_lang.lower(),
                    "text": text,
                    "image": None
                }]
            },
        ]
        
        # Tokenize using TranslateGemma's chat template
        # apply_chat_template returns a BatchEncoding; we need the raw input_ids tensor
        encoded = self._tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
            tokenize=True,
            add_generation_prompt=True
        )
        # BatchEncoding has an input_ids attribute; plain tensors do not
        inputs = {}
        if hasattr(encoded, 'input_ids'):
            inputs['input_ids'] = encoded.input_ids
            inputs['attention_mask'] = encoded.attention_mask
        else:
            inputs['input_ids'] = encoded
        
        if self._device != 'cpu':
            for k, v in inputs.items():
                inputs[k] = v.to(self._model.device)
        
        # Generate (max_new_tokens=256 is sufficient for any segment/verse)
        print(f"DEBUG: Starting generation for '{text[:50]}...'")
        outputs = self._model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            temperature=None,
            pad_token_id=self._tokenizer.eos_token_id
        )
        
        # Decode only the new tokens
        input_ids = inputs['input_ids']
        generated_ids = outputs[0][input_ids.shape[1]:]
        response = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
        print(f"DEBUG: Generation complete: '{response[:50]}...'")
        
        translation_time_ms = int((time.time() - start_time) * 1000)
        
        return response.strip(), translation_time_ms
    
    def translate_batch(self, texts: list, target_lang: str = "es",
                        progress_callback=None) -> list:
        """
        Translate multiple texts.
        
        Args:
            texts: List of source texts
            target_lang: Target language code
            progress_callback: Optional callback(index, total, translation)
        
        Returns:
            List of (translation, time_ms) tuples
        """
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            translation, time_ms = self.translate(text, target_lang)
            results.append((translation, time_ms))
            
            if progress_callback:
                progress_callback(i + 1, total, translation)
        
        return results
    
    @staticmethod
    def download_model():
        """Download model files explicitly."""
        from huggingface_hub import snapshot_download
        print(f"Downloading model {MODEL_ID}...")
        snapshot_download(repo_id=MODEL_ID)
        print("Download complete.")
    
    def unload(self):
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        
        # Clear CUDA cache if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        
        print("Model unloaded")


if __name__ == "__main__":
    # Test script
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--download":
        GemmaService.download_model()
    else:
        print("Testing Gemma Translation Service...")
        service = GemmaService()
        service.initialize()
        
        test_text = "Hello, how are you today?"
        translation, time_ms = service.translate(test_text, "es")
        
        print(f"\nSource: {test_text}")
        print(f"Translation: {translation}")
        print(f"Time: {time_ms}ms")
        print(f"\nDevice info: {service.device_info}")
