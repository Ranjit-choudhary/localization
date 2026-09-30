import os
import time
import pandas as pd
import ollama

# 1. Configuration: Add up to 3-4 LLMs to this list for your benchmark comparison
MODELS = ["llama3.2"]  

# The 12 target languages required for your global benchmark
TARGET_LANGUAGES = {
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
    "mr": "Marathi",
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
                "top_p": 0.9
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
    
    # MODIFIED: Removed the .iloc[:5] limit. This now grabs every row in the first column.
    source_strings = df_raw.iloc[:, 0].dropna().astype(str).tolist()

    print(f"Loaded {len(source_strings)} source strings from the dataset.")

    # Loop through each language
    for lang_code, lang_name in TARGET_LANGUAGES.items():
        print(f"\n--- Processing Language: {lang_name} ---")
        
        output_file = f"translations_{lang_name.lower()}.csv"
        
        if not os.path.exists(output_file):
            pd.DataFrame(columns=[
                "string_id", "source_en", "lang_code", "target_language", "model", "translation", "latency_sec"
            ]).to_csv(output_file, index=False)

        for str_id, src_text in enumerate(source_strings):
            messages = get_translation_messages(src_text, lang_name)
            
            for model in MODELS:
                print(f"[{str_id + 1}/{len(source_strings)}] {model} -> {lang_code} ({lang_name})...")
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

                # Append result incrementally 
                row.to_csv(output_file, mode="a", header=False, index=False)

    print("\nBenchmark complete. All 12 language files have been generated.")

if __name__ == "__main__":
    main()