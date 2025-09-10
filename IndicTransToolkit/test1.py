import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit import IndicProcessor

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

src_lang, tgt_lang = "eng_Latn", "hin_Deva"
model_name = "ai4bharat/indictrans2-en-indic-dist-200M"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

model = AutoModelForSeq2SeqLM.from_pretrained(
    model_name, 
    trust_remote_code=True,
    dtype=torch.float16
).to(DEVICE)

ip = IndicProcessor(inference=True)

input_sentences = [
    "When I was young, I used to go to the park every day.",
    "We watched a new movie last week, which was very inspiring.",
    "If you had met me at that time, we would have gone out to eat.",
    "My friend has invited me to his birthday party, and I will give him a gift.",
]

batch = ip.preprocess_batch(input_sentences, src_lang=src_lang, tgt_lang=tgt_lang)

inputs = tokenizer(
    batch,
    truncation=True,
    padding="longest",
    return_tensors="pt",
    return_attention_mask=True,
).to(DEVICE)

with torch.no_grad(), torch.autocast("cuda"):
    # Step 1: Encoder outputs
    encoder_outputs = model.get_encoder()(**inputs)

    # Step 2: Greedy decoding loop
    generated_ids = torch.full(
        (inputs['input_ids'].size(0), 1),
        tokenizer.pad_token_id,
        dtype=torch.long,
        device=DEVICE
    )

    max_length = 256
    for _ in range(max_length):
        decoder_inputs = {'input_ids': generated_ids}
        decoder_outputs = model.model.decoder(
            input_ids=generated_ids,
            encoder_hidden_states=encoder_outputs.last_hidden_state,
        )

        logits = model.lm_head(decoder_outputs.last_hidden_state[:, -1, :])  # logits for next token
        next_token_id = torch.argmax(logits, dim=-1).unsqueeze(-1)
        generated_ids = torch.cat([generated_ids, next_token_id], dim=-1)

        # Stop early if all sequences generated EOS token
        if (next_token_id == tokenizer.eos_token_id).all():
            break

generated_tokens = tokenizer.batch_decode(
    generated_ids,
    skip_special_tokens=True,
    clean_up_tokenization_spaces=True,
)

translations = ip.postprocess_batch(generated_tokens, lang=tgt_lang)

for input_sentence, translation in zip(input_sentences, translations):
    print(f"{src_lang}: {input_sentence}")
    print(f"{tgt_lang}: {translation}")
