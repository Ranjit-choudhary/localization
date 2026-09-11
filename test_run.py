import os
import time
import pandas as pd
import ollama

# 1. Configuration: Your specific models and batch
# MODELS = ["llama3.2", "qwen2.5-coder:7b", "translategemma:4b"]
MODELS = ["qwen2.5-coder:7b"]

TARGET_LANGUAGES = {
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
    "ar": "Arabic",
    "bn": "Bengali",
    "de": "German",
    "mr:": "Marathi",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "zh": "Chinese",
}

INPUT_FILE = "Dataset-Translated.xlsx"

# 2. Strict UI/Software Localization System Prompt
SYSTEM_PROMPT = """You are an expert software localization engine.
Translate the user interface (UI) text from English to the specified target language.

RULES:
1. Preserve all format specifiers, code, tags, and placeholders exactly as they are (e.g., %s, %d, {count}, <b>...</b>, &File).
2. Keep the translation concise, natural, and suited for software interfaces.
3. Return ONLY the translated string. Do NOT add greetings, quotes, or explanations."""

def get_translation_messages(source_text: str, target_lang_name: str) -> list:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Target Language: {target_lang_name}\nSource Text: \"{source_text}\"\nTranslation:"
        }
    ]

def query_ollama(model_name: str, messages: list) -> tuple[str, float]:
    start = time.time()
    try:
        response = ollama.chat(
            model=model_name,
            messages=messages,
            options={
                "temperature": 0.0,
                "top_p": 0.9,
                "num_predict": 100
            }
        )
        latency = round(time.time() - start, 3)
        raw_output = response["message"]["content"].strip()
        cleaned_output = raw_output.strip('"\'')
        return cleaned_output, latency
    except Exception as e:
        print(f"  [Error] {model_name}: {e}")
        return "", 0.0

def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Cannot find input file: {INPUT_FILE}")

    df_raw = pd.read_excel(INPUT_FILE)
    source_strings = df_raw.iloc[:, 0].dropna().astype(str).tolist()

    print(f"Loaded {len(source_strings)} source strings from the dataset.")

    for lang_code, lang_name in TARGET_LANGUAGES.items():
        print(f"\n--- Processing Language: {lang_name} ---")
        output_file = f"translations_{lang_name.lower()}.csv"
        
        # 1. CHECKPOINT LOGIC
        completed_translations = set()
        if os.path.exists(output_file):
            try:
                df_existing = pd.read_csv(output_file)
                for index, row in df_existing.iterrows():
                    completed_translations.add(f"{row['string_id']}_{row['model']}")
            except Exception as e:
                print(f"Could not read existing file {output_file}: {e}")
        else:
            pd.DataFrame(columns=[
                "string_id", "source_en", "lang_code", "target_language", "model", "translation", "latency_sec"
            ]).to_csv(output_file, index=False)

        
        for model in MODELS:
            print(f"\n>> Loading {model} into memory...")
            
            for str_id, src_text in enumerate(source_strings):
                if f"{str_id}_{model}" in completed_translations:
                    # Silently skip to avoid spamming the terminal
                    continue
                
                messages = get_translation_messages(src_text, lang_name)
                
                print(f"Translating [{str_id + 1}/{len(source_strings)}] {model} -> {lang_code} ({lang_name})...")
                translation, latency = query_ollama(model, messages)

                row = pd.DataFrame([{
                    "string_id": str_id,
                    "source_en": src_text,
                    "lang_code": lang_code,
                    "target_language": lang_name,
                    "model": model,
                    "translation": translation,
                    "latency_sec": latency
                }])

                row.to_csv(output_file, mode="a", header=False, index=False)
                
                # Sleep reduced to 0.1s since your temps are a very safe 61°C
                # time.sleep(0.5)
    print("\nBenchmark complete. Check your CSV files for the results.")
if __name__ == "__main__":
    main()