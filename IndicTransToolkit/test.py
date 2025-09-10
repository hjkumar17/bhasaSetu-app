import torch
from IndicTransToolkit import IndicProcessor  # Cython compiled
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

device = "cpu"  # Use "cuda" if GPU is available

print("Initializing IndicProcessor...")
ip = IndicProcessor(inference=True)

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    "ai4bharat/indictrans2-en-indic-dist-200M", trust_remote_code=True
)

print("Loading model...")
model = AutoModelForSeq2SeqLM.from_pretrained(
    "ai4bharat/indictrans2-en-indic-dist-200M", trust_remote_code=True
).to(device)

# Sample sentences for translation
sentences = [
    "This is a test sentence.",
    "This is another longer different test sentence.",
    "Please send an SMS to 9876543210 and an email on newemail123@xyz.com by 15th October, 2023.",
]

print("Preprocessing sentences...")
batch_sentences = ip.preprocess_batch(
    sentences, src_lang="eng_Latn", tgt_lang="hin_Deva", visualize=False
)
print(f"Preprocessed batch: {batch_sentences}")

print("Tokenizing...")
batch = tokenizer(
    batch_sentences,
    padding="longest",
    truncation=True,
    max_length=256,
    return_tensors="pt"
).to(device)

print("Generating translations...")
with torch.inference_mode():
    outputs = model.generate(
        **batch,
        num_beams=5,
        num_return_sequences=1,
        max_length=256,
        use_cache=False  # Important: disables past_key_values to prevent crash
    )

print("Decoding outputs...")
decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True, clean_up_tokenization_spaces=True)

print("Postprocessing translations...")
final_outputs = ip.postprocess_batch(decoded, lang="hin_Deva")

print("\nFinal Translations:")
for orig, trans in zip(sentences, final_outputs):
    print(f"EN: {orig}")
    print(f"HI: {trans}")
    print("-" * 50)
