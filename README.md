# Prompt2OpenSCENARIO Preprocessing Toolkit

## Overview

This repository contains a comprehensive preprocessing pipeline designed to construct and validate datasets for **fine-tuning large language models (LLMs)** on the task of generating **OpenSCENARIO 1.0 (`.xosc`) files** from natural language descriptions.  
The goal of the project is to create high-quality instruction–response pairs where the **input** is an English scenario description and the **output** is a schema-compliant `.xosc` file executable in the **CARLA simulator**.  

The toolkit ensures that the resulting dataset is both **syntactically valid** (via XSD checks) and **semantically diverse** (via data augmentation strategies such as entity injection, weather/time perturbations, and reduction rules).  

---

## Motivation

Autonomous driving simulation requires a rich variety of realistic and reproducible scenarios. While **OpenSCENARIO** provides a standard XML-based specification for scenarios, authoring `.xosc` files manually is time-consuming and error-prone. By leveraging **LLMs fine-tuned on paired data (description ↔ scenario)**, we aim to automate scenario generation, enabling:

- **Rapid prototyping** of safety-critical driving situations.
- **Diversity and scalability** in simulation-based testing pipelines.
- **Natural language accessibility**, lowering the entry barrier for scenario creation.

---

## Repository Structure

The repository is organized around modular scripts for **validation, reduction, augmentation, description extraction, and dataset assembly**:

- **`xsd_validator.py`**  
  Core validator that checks `.xosc` files against the official OpenSCENARIO XSD.

- **`xsd_filter.py`**  
  Filters `.xosc` files, exporting only those that are schema-compliant.

- **`inject_diversity.py`**  
  Introduces controlled diversity by modifying weather, time of day, pedestrians, and fog parameters while ensuring XSD validity.

- **`reduce_xosc.py`**  
  Applies reduction rules to scenarios (e.g., pruning redundant vehicles, entities, and stories) while retaining semantic integrity.

- **`xosc_describer.py`**  
  Extracts salient scenario features (map, entities, weather, events, etc.) and produces a **compact prompt** representation.

- **`build_dataset.py`**  
  Generates the final dataset in **JSONL format** by pairing natural language descriptions (obtained via GPT-based summarization of features) with corresponding `.xosc` files.  
  Each record includes:
  - `system`: system prompt for the model  
  - `user`: natural language description  
  - `assistant`: schema-compliant `.xosc` file  

- **`dataset_validator.py`**  
  Verifies that all `.xosc` entries in the dataset remain XSD-compliant.

- **`compute_xosc_diversity.py`**  
  Computes diversity statistics across entities, weather conditions, and temporal configurations in the dataset.

- **`unused_tags.py`**  
  Identifies unused tags in the dataset compared to the OpenSCENARIO XSD, highlighting potential underrepresented structures.

---

## Workflow

The preprocessing workflow follows a sequential pipeline:

1. **Validation**  
   - Use `xsd_filter.py` and `xsd_validator.py` to retain only valid `.xosc` files.  

2. **Diversity Injection**  
   - Apply `inject_diversity.py` to enrich the dataset with varied weather, pedestrians, and temporal contexts.  

3. **Reduction**  
   - Simplify scenarios with `reduce_xosc.py` to focus on essential entities while preserving realism.  

4. **Feature Extraction & Prompt Construction**  
   - Run `xosc_describer.py` to extract scenario features and generate compact structured prompts.  

5. **Dataset Assembly**  
   - Execute `build_dataset.py` to pair GPT-generated English descriptions with `.xosc` files into a JSONL dataset.  

6. **Final Validation**  
   - Check the dataset with `dataset_validator.py` to guarantee schema compliance.  

---
---

## Reverse Dataset Construction (XOSC → English)

In addition to the main pipeline (natural language description → OpenSCENARIO), this repository also provides a utility for constructing the **inverse dataset**, where the input is an `.xosc` file and the output is a natural language description of the scenario.  

This reversed dataset enables the fine-tuning of a complementary LLM that performs the opposite task:  
- **Input:** schema-compliant OpenSCENARIO 1.0 file  
- **Output:** plain-text English description of the scenario (4–5 sentences, 50–100 words)  

Such a model is valuable for **evaluating the coherence** of the generative process: if the forward model (description → XOSC) produces a scenario, the reverse model (XOSC → description) can be used to assess whether the generated `.xosc` indeed corresponds to the original description.

Output format:

```json
{
  "system": "Act as an OpenSCENARIO 1.0 scenario analyst for the CARLA simulator...",
  "user": "<OpenScenario> ... </OpenScenario>",
  "assistant": "A natural language description (50–100 words)..."
}
```

---

## Dataset Format

The resulting dataset is a `.jsonl` file where each record follows the structure:

```json
{
  "system": "Act as an OpenSCENARIO 1.0 generator for ADS testing in CARLA...",
  "user": "A natural language description of the scene (50–100 words)...",
  "assistant": "<OpenScenario> ... </OpenScenario>"
}
```

This format is directly compatible with instruction-tuning frameworks such as Hugging Face Transformers, PEFT/LoRA, or TRL.

## Acknowledgments
This work builds on the OpenSCENARIO 1.0 standard and leverages the CARLA simulator as the target execution platform. We acknowledge the role of Hugging Face ecosystem in supporting dataset hosting and model distribution.