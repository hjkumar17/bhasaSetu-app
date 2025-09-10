import sys
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, BitsAndBytesConfig
from transformers.utils import is_flash_attn_2_available, is_flash_attn_greater_or_equal_2_10
from IndicTransToolkit import IndicProcessor
from mosestokenizer import MosesSentenceSplitter
from nltk import sent_tokenize
from indicnlp.tokenize.sentence_tokenize import sentence_split, DELIM_PAT_NO_DANDA

print("=== Step 1: Imports done ===")

en_indic_ckpt_dir = "ai4bharat/indictrans2-en-indic-dist-200M"
indic_en_ckpt_dir = "ai4bharat/indictrans2-indic-en-dist-200M"
indic_indic_ckpt_dir = "ai4bharat/indictrans2-indic-indic-dist-320M"
BATCH_SIZE = 4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"=== Step 2: Device set to {DEVICE}, Batch size = {BATCH_SIZE} ===")

if len(sys.argv) > 1:
    quantization = sys.argv[1]
    attn_implementation = sys.argv[2]
else:
    quantization = ""
    attn_implementation = "eager"

print(f"=== Step 3: Quantization = '{quantization}', Attention = '{attn_implementation}' ===")

# FLORES language code mapping (unchanged)
flores_codes = {
    "asm_Beng": "as",
    "awa_Deva": "hi",
    "ben_Beng": "bn",
    "bho_Deva": "hi",
    "brx_Deva": "hi",
    "doi_Deva": "hi",
    "eng_Latn": "en",
    "gom_Deva": "kK",
    "guj_Gujr": "gu",
    "hin_Deva": "hi",
    "hne_Deva": "hi",
    "kan_Knda": "kn",
    "kas_Arab": "ur",
    "kas_Deva": "hi",
    "kha_Latn": "en",
    "lus_Latn": "en",
    "mag_Deva": "hi",
    "mai_Deva": "hi",
    "mal_Mlym": "ml",
    "mar_Deva": "mr",
    "mni_Beng": "bn",
    "mni_Mtei": "hi",
    "npi_Deva": "ne",
    "ory_Orya": "or",
    "pan_Guru": "pa",
    "san_Deva": "hi",
    "sat_Olck": "or",
    "snd_Arab": "ur",
    "snd_Deva": "hi",
    "tam_Taml": "ta",
    "tel_Telu": "te",
    "urd_Arab": "ur",
}


def split_sentences(input_text, lang):
    print(f"Splitting sentences for language: {lang}")
    if lang == "eng_Latn":
        input_sentences = sent_tokenize(input_text)
        with MosesSentenceSplitter(flores_codes[lang]) as splitter:
            sents_moses = splitter([input_text])
        sents_nltk = sent_tokenize(input_text)
        if len(sents_nltk) < len(sents_moses):
            input_sentences = sents_nltk
        else:
            input_sentences = sents_moses
        input_sentences = [sent.replace("\xad", "") for sent in input_sentences]
    else:
        input_sentences = sentence_split(
            input_text, lang=flores_codes[lang], delim_pat=DELIM_PAT_NO_DANDA
        )
    print(f"Found {len(input_sentences)} sentences")
    return input_sentences


def initialize_model_and_tokenizer(ckpt_dir, quantization, attn_implementation):
    print(f"Initializing model from checkpoint: {ckpt_dir}")
    if quantization == "4-bit":
        qconfig = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    elif quantization == "8-bit":
        qconfig = BitsAndBytesConfig(
            load_in_8bit=True,
            bnb_8bit_use_double_quant=True,
            bnb_8bit_compute_dtype=torch.bfloat16,
        )
    else:
        qconfig = None 

    if attn_implementation == "flash_attention_2":
        if is_flash_attn_2_available() and is_flash_attn_greater_or_equal_2_10():
            attn_implementation = "flash_attention_2"
        else:
            attn_implementation = "eager"

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(ckpt_dir, trust_remote_code=True)
    print("Loading model...")
    model = AutoModelForSeq2SeqLM.from_pretrained(
        ckpt_dir,
        trust_remote_code=True,
        attn_implementation="eager",
        low_cpu_mem_usage=True,
        quantization_config=qconfig,
    )

    if qconfig is None:
        model = model.to(DEVICE)
        model.half()
    model.eval()
    print("Model and tokenizer loaded successfully")
    return tokenizer, model


def batch_translate(input_sentences, src_lang, tgt_lang, model, tokenizer, ip):
    print(f"Translating batch from {src_lang} to {tgt_lang}")
    translations = []
    for i in range(0, len(input_sentences), BATCH_SIZE):
        batch = input_sentences[i : i + BATCH_SIZE]
        print(f"Processing batch {i // BATCH_SIZE + 1}, size = {len(batch)}")

        batch = ip.preprocess_batch(batch, src_lang=src_lang, tgt_lang=tgt_lang)
        inputs = tokenizer(
            batch,
            truncation=True,
            padding="longest",
            return_tensors="pt",
            return_attention_mask=True,
        ).to(DEVICE)
        print("Tokenization complete")

        with torch.no_grad():
            generated_tokens = model.generate(
                **inputs,
                use_cache=False,
                min_length=0,
                max_length=256,
                num_beams=5,
                num_return_sequences=1,
            )
        print("Generation complete")

        generated_tokens = tokenizer.batch_decode(
            generated_tokens,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        translations += ip.postprocess_batch(generated_tokens, lang=tgt_lang)
        print(f"Batch {i // BATCH_SIZE + 1} translated")

        del inputs
        torch.cuda.empty_cache()
    return translations


def translate_paragraph(input_text, src_lang, tgt_lang, model, tokenizer, ip):
    print("Translating paragraph...")
    input_sentences = split_sentences(input_text, src_lang)
    translated_text = batch_translate(input_sentences, src_lang, tgt_lang, model, tokenizer, ip)
    return " ".join(translated_text)


# Initialize IndicProcessor
print("Initializing IndicProcessor...")
ip = IndicProcessor(inference=True)

# Initialize models
en_indic_tokenizer, en_indic_model = initialize_model_and_tokenizer(
    en_indic_ckpt_dir, quantization, attn_implementation
)
indic_en_tokenizer, indic_en_model = initialize_model_and_tokenizer(
    indic_en_ckpt_dir, quantization, attn_implementation
)
indic_indic_tokenizer, indic_indic_model = initialize_model_and_tokenizer(
    indic_indic_ckpt_dir, quantization, attn_implementation
)

print("=== Models initialized successfully ===")

# ---------------------------------------------------------------------------
# Hindi to English
# ---------------------------------------------------------------------------
print("\n=== Hindi to English Translation Test ===")
hi_sents = [
    "जब मैं छोटा था, मैं हर रोज़ पार्क जाता था।",
    "उसके पास बहुत सारी पुरानी किताबें हैं, जिन्हें उसने अपने दादा-परदादा से विरासत में पाया।",
    "मुझे समझ में नहीं आ रहा कि मैं अपनी समस्या का समाधान कैसे ढूंढूं।",
    "वह बहुत मेहनती और समझदार है, इसलिए उसे सभी अच्छे मार्क्स मिले।",
    "हमने पिछले सप्ताह एक नई फिल्म देखी जो कि बहुत प्रेरणादायक थी।",
    "अगर तुम मुझे उस समय पास मिलते, तो हम बाहर खाना खाने चलते।",
    "वह अपनी दीदी के साथ बाजार गयी थी ताकि वह नई साड़ी खरीद सके।",
    "राज ने मुझसे कहा कि वह अगले महीने अपनी नानी के घर जा रहा है।",
    "सभी बच्चे पार्टी में मज़ा कर रहे थे और खूब सारी मिठाइयाँ खा रहे थे।",
    "मेरे मित्र ने मुझे उसके जन्मदिन की पार्टी में बुलाया है, और मैं उसे एक तोहफा दूंगा।",
]
src_lang, tgt_lang = "hin_Deva", "eng_Latn"
print(f"Translating {len(hi_sents)} sentences from {src_lang} to {tgt_lang}...")
en_translations = batch_translate(
    hi_sents, src_lang, tgt_lang, indic_en_model, indic_en_tokenizer, ip
)
for input_sentence, translation in zip(hi_sents, en_translations):
    print(f"{src_lang}: {input_sentence}")
    print(f"{tgt_lang}: {translation}")
print("=== Hindi to English Translation Done ===")

# ---------------------------------------------------------------------------
# English to Hindi
# ---------------------------------------------------------------------------
print("\n=== English to Hindi Translation Test ===")
en_sents = [
    "When I was young, I used to go to the park every day.",
    "He has many old books, which he inherited from his ancestors.",
    "I can't figure out how to solve my problem.",
    "She is very hardworking and intelligent, which is why she got all the good marks.",
    "We watched a new movie last week, which was very inspiring.",
    "If you had met me at that time, we would have gone out to eat.",
    "She went to the market with her sister to buy a new sari.",
    "Raj told me that he is going to his grandmother's house next month.",
    "All the kids were having fun at the party and were eating lots of sweets.",
    "My friend has invited me to his birthday party, and I will give him a gift.",
]
src_lang, tgt_lang = "eng_Latn", "hin_Deva"
print(f"Translating {len(en_sents)} sentences from {src_lang} to {tgt_lang}...")
hi_translations = batch_translate(
    en_sents, src_lang, tgt_lang, en_indic_model, en_indic_tokenizer, ip
)
for input_sentence, translation in zip(en_sents, hi_translations):
    print(f"{src_lang}: {input_sentence}")
    print(f"{tgt_lang}: {translation}")
print("=== English to Hindi Translation Done ===")

# ---------------------------------------------------------------------------
# Hindi to Marathi
# ---------------------------------------------------------------------------
print("\n=== Hindi to Marathi Translation Test ===")
hi_sents = [
    "जब मैं छोटा था, मैं हर रोज़ पार्क जाता था।",
    "उसके पास बहुत सारी पुरानी किताबें हैं, जिन्हें उसने अपने दादा-परदादा से विरासत में पाया।",
    "मुझे समझ में नहीं आ रहा कि मैं अपनी समस्या का समाधान कैसे ढूंढूं।",
    "वह बहुत मेहनती और समझदार है, इसलिए उसे सभी अच्छे मार्क्स मिले।",
    "हमने पिछले सप्ताह एक नई फिल्म देखी जो कि बहुत प्रेरणादायक थी।",
    "अगर तुम मुझे उस समय पास मिलते, तो हम बाहर खाना खाने चलते।",
    "वह अपनी दीदी के साथ बाजार गयी थी ताकि वह नई साड़ी खरीद सके।",
    "राज ने मुझसे कहा कि वह अगले महीने अपनी नानी के घर जा रहा है।",
    "सभी बच्चे पार्टी में मज़ा कर रहे थे और खूब सारी मिठाइयाँ खा रहे थे।",
    "मेरे मित्र ने मुझे उसके जन्मदिन की पार्टी में बुलाया है, और मैं उसे एक तोहफा दूंगा।",
]
src_lang, tgt_lang = "hin_Deva", "mar_Deva"
print(f"Translating {len(hi_sents)} sentences from {src_lang} to {tgt_lang}...")
mr_translations = batch_translate(
    hi_sents, src_lang, tgt_lang, indic_indic_model, indic_indic_tokenizer, ip
)
for input_sentence, translation in zip(hi_sents, mr_translations):
    print(f"{src_lang}: {input_sentence}")
    print(f"{tgt_lang}: {translation}")
print("=== Hindi to Marathi Translation Done ===")

# ---------------------------------------------------------------------------
# Paragraph translation
# ---------------------------------------------------------------------------
print("\n=== Paragraph Translation Test ===")
src_lang, tgt_lang = "hin_Deva", "eng_Latn"
hi_text = "यहाँ एक पाराग्राफ है जो हिंदी में लिखा गया है। हिंदी एक सुंदर भाषा है और भारत की राष्ट्रीय भाषा है। इसका विकास विभिन्न कालों में हुआ है और यह विशेषतः भारतीय उपमहाद्वीप में बोली जाती है। हिंदी भाषा का साहित्य, संस्कृति और इतिहास भी बहुत गर्वनीय है।"
print(f"Translating paragraph from {src_lang} to {tgt_lang}...")
en_translated_text = translate_paragraph(
    hi_text, src_lang, tgt_lang, indic_en_model, indic_en_tokenizer, ip
)
print(f"{src_lang}: {hi_text}")
print(f"{tgt_lang}: {en_translated_text}")
print("=== Paragraph Translation Done ===")
