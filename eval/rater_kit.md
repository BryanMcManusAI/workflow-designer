# Workflow Designer — Gold Audit Kit

You're confirming the answer key for the recommendation eval. For each workflow below, judge:

1. **Analogous recipes** — is each drafted recipe a genuinely useful prior example for this workflow? Mark **Y** (yes, relevant) or **N** (no). Add any the draft missed.

2. **Risks** — does each drafted failure risk genuinely apply to this kind of workflow? **Y** / **N**. Add any missed.

Polarity is uniform: **Y = relevant / applies, N = not.** Appendices list the full option space (every recipe, every risk) so you can add from a known menu.


---


## 1. tox-moderation

> **Goal:** Crowd-label user comments as toxic or hateful to train a content-moderation classifier  

> text / classification / crowd


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `content-moderation-abuse` — Abusive-Language / Hate-Speech Annotation   **Y / N**
- [ ] `content-moderation-welfare-ops` — Commercial Content Moderation (Decisions + Moderator Welfare)   **Y / N**
- [ ] `crowd-quality-mturk` — Crowd Data Collection Under the MTurk Quality Crisis   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `under_specification` — so loose competent annotators disagree (low IAA)   **Y / N**
- [ ] `drift` — guidelines / acceptance bar move over the campaign   **Y / N**
- [ ] `gaming` — annotators optimize the pay/quota, not quality (Goodhart)   **Y / N**
- [ ] `sampling_frame` — the labeled set isn't representative of deployment   **Y / N**
- _Add others:_ ______________________________________________


---


## 2. detection-bbox

> **Goal:** Draw bounding boxes around vehicles and pedestrians in street images for an object detector  

> image / structured_output / tiered_review


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `image-bbox-adjudicated` — Object Bounding-Box Labeling with Redundancy + Adjudication   **Y / N**
- [ ] `pointcloud-detection-nuscenes` — Multi-Sensor 3D Bounding-Box Annotation (nuScenes)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `under_specification` — so loose competent annotators disagree (low IAA)   **Y / N**
- [ ] `class_imbalance` — rare-but-important classes under-sampled   **Y / N**
- [ ] `sampling_frame` — the labeled set isn't representative of deployment   **Y / N**
- [ ] `bottleneck` — one stage (adjudication, expert review) gates throughput   **Y / N**
- _Add others:_ ______________________________________________


---


## 3. rlhf-preference

> **Goal:** Collect human preference pairs between two chatbot responses to train a reward model  

> text / preference_ranking / crowd


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `text-preference-rlhf` — Pairwise Preference Collection for RLHF   **Y / N**
- [ ] `preference-anthropic-hh` — Preference Collection — Anthropic HH-RLHF   **Y / N**
- [ ] `preference-llama2-rlhf` — Preference Collection — Meta Llama 2 RLHF   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `confounded` — a spurious cue (length, source, tier) rides along with the real signal   **Y / N**
- [ ] `drift` — guidelines / acceptance bar move over the campaign   **Y / N**
- [ ] `priming` — item order or position contaminates the label   **Y / N**
- [ ] `unanchored` — no gold / ground truth to check labels against   **Y / N**
- _Add others:_ ______________________________________________


---


## 4. clinical-extraction

> **Goal:** Have clinicians annotate disease and medication mentions in clinical notes  

> text / extraction / expert


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `clinical-annotation-guidelines` — Clinical Text Annotation with Iterative Guidelines + Adjudication   **Y / N**
- [ ] `ner-conll2003` — Expert Span Annotation for NER (CoNLL-2003)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `under_specification` — so loose competent annotators disagree (low IAA)   **Y / N**
- [ ] `class_imbalance` — rare-but-important classes under-sampled   **Y / N**
- [ ] `bottleneck` — one stage (adjudication, expert review) gates throughput   **Y / N**
- _Add others:_ ______________________________________________


---


## 5. code-eval

> **Goal:** Build an eval set of coding problems with unit tests to measure model code generation  

> code / freeform_generation / expert


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `code-humaneval` — Execution-Verified Code-Generation Eval Set (HumanEval)   **Y / N**
- [ ] `code-swebench` — Harvested GitHub Issues, Execution-Verified (SWE-bench)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `label_leakage` — the label is derivable from a feature it shouldn't be / eval contaminated by training   **Y / N**
- [ ] `under_specification` — so loose competent annotators disagree (low IAA)   **Y / N**
- _Add others:_ ______________________________________________


---


## 6. speech-transcription

> **Goal:** Crowd-transcribe short audio clips to build a speech-recognition training set  

> audio / transcription_translation / crowd


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `audio-transcription-commonvoice` — Crowdsourced Read-Speech Corpus with Vote Validation (Common Voice)   **Y / N**
- [ ] `speech-librispeech` — Speech Data by Forced Alignment to Existing Text (LibriSpeech)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `class_imbalance` — rare-but-important classes under-sampled   **Y / N**
- [ ] `sampling_frame` — the labeled set isn't representative of deployment   **Y / N**
- [ ] `under_specification` — so loose competent annotators disagree (low IAA)   **Y / N**
- _Add others:_ ______________________________________________


---


## 7. llm-judge-rating

> **Goal:** Use an LLM to rate the quality of AI-generated marketing emails at scale  

> text / rubric_rating / model_as_annotator


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `judge-eval-study` — LLM-as-Judge Evaluation Study   **Y / N**
- [ ] `eval-chatbot-arena` — Open Crowd Pairwise Battles + LLM-Judge (Chatbot Arena / MT-Bench)   **Y / N**
- [ ] `critique-criticgpt` — Critique-Rationale Collection via Bug Tampering (CriticGPT)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `self_affinity` — a model judge favors its own family's outputs   **Y / N**
- [ ] `unanchored` — no gold / ground truth to check labels against   **Y / N**
- [ ] `inflation` — the bar creeps up; everything starts passing   **Y / N**
- [ ] `confounded` — a spurious cue (length, source, tier) rides along with the real signal   **Y / N**
- _Add others:_ ______________________________________________


---


## 8. redteam-chatbot

> **Goal:** Run a red team to find prompts that make a chatbot produce harmful content  

> text / red_team / crowd


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `redteam-adversarial-dialogue` — Crowdsourced Adversarial Red-Team Dialogue Collection   **Y / N**
- [ ] `redteam-automated-perez` — Red-Teaming — Automated (LM-Generated Attacks)   **Y / N**
- [ ] `redteam-external-gpt4` — Red-Teaming — External Domain-Expert Network   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `sampling_frame` — the labeled set isn't representative of deployment   **Y / N**
- [ ] `gaming` — annotators optimize the pay/quota, not quality (Goodhart)   **Y / N**
- _Add others:_ ______________________________________________


---


## 9. synthetic-instructions

> **Goal:** Generate synthetic instruction-tuning data with a model and audit a sample  

> text / demonstration / model_as_annotator


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `synthetic-with-audit` — Model-Generated Labels with Human Audit   **Y / N**
- [ ] `synthetic-textbooks-phi` — Model-Generated + Model-Filtered Training Data (phi / Textbooks)   **Y / N**
- [ ] `instruction-self-instruct` — Instruction Data — Synthetic Bootstrap (Self-Instruct / Alpaca)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `confounded` — a spurious cue (length, source, tier) rides along with the real signal   **Y / N**
- [ ] `unanchored` — no gold / ground truth to check labels against   **Y / N**
- [ ] `label_leakage` — the label is derivable from a feature it shouldn't be / eval contaminated by training   **Y / N**
- [ ] `sampling_frame` — the labeled set isn't representative of deployment   **Y / N**
- _Add others:_ ______________________________________________


---


## 10. search-relevance

> **Goal:** Have annotators grade how relevant documents are to search queries  

> text / relevance / crowd


**Analogous recipes** (mark Y/N, strike-through to drop):

- [ ] `relevance-pooling-trec` — TREC-Style Relevance Judgments via Pooling   **Y / N**
- [ ] `search-msmarco` — Relevance + Answers from Real Query Logs (MS MARCO)   **Y / N**
- _Add others:_ ______________________________________________


**Risks that genuinely apply** (mark Y/N):

- [ ] `sampling_frame` — the labeled set isn't representative of deployment   **Y / N**
- [ ] `under_specification` — so loose competent annotators disagree (low IAA)   **Y / N**
- [ ] `priming` — item order or position contaminates the label   **Y / N**
- _Add others:_ ______________________________________________


---


## Appendix A — every recipe (the menu for 'add others')

- `adversarial-nli-anli` — Human-and-Model-in-the-Loop Adversarial NLI (ANLI) [text/classification]
- `audio-transcription-commonvoice` — Crowdsourced Read-Speech Corpus with Vote Validation (Common Voice) [audio/transcription_translation]
- `benchmark-bigbench` — Community-Contributed Eval Benchmark (BIG-bench) [text/freeform_generation]
- `clinical-annotation-guidelines` — Clinical Text Annotation with Iterative Guidelines + Adjudication [text/extraction]
- `clinical-chexpert-labeler` — Image Labels from Reports via Rule-Based NLP (CheXpert) [image/classification]
- `code-humaneval` — Execution-Verified Code-Generation Eval Set (HumanEval) [code/freeform_generation]
- `code-swebench` — Harvested GitHub Issues, Execution-Verified (SWE-bench) [code/freeform_generation]
- `content-moderation-abuse` — Abusive-Language / Hate-Speech Annotation [text/classification]
- `content-moderation-welfare-ops` — Commercial Content Moderation (Decisions + Moderator Welfare) [multimodal/classification]
- `corpus-ingestion` — Corpus Ingestion — Source Documents to Curated Workflow Cards [text/extraction]
- `critique-criticgpt` — Critique-Rationale Collection via Bug Tampering (CriticGPT) [code/critique_rationale]
- `crowd-aggregation-dawid-skene` — Probabilistic Label Aggregation (Dawid-Skene) [text/classification]
- `crowd-quality-mturk` — Crowd Data Collection Under the MTurk Quality Crisis [text/classification]
- `data-quality-cleanlab` — Find NATURAL Label Errors via Confident Learning (CleanLab) [tabular/classification]
- `datasheets-documentation` — Dataset Documentation & Provenance (Datasheets for Datasets) [text/extraction]
- `demonstration-instructgpt` — Screened-Contractor Demonstrations + Comparisons (InstructGPT) [text/demonstration]
- `detector-planted-mislabels` — Planted-Mislabel Injection for Bad-Data Detection [tabular/classification]
- `eval-chatbot-arena` — Open Crowd Pairwise Battles + LLM-Judge (Chatbot Arena / MT-Bench) [text/preference_ranking]
- `image-bbox-adjudicated` — Object Bounding-Box Labeling with Redundancy + Adjudication [image/structured_output]
- `image-classification-imagenet` — Crowdsourced Image Classification against an Ontology (ImageNet) [image/classification]
- `instruction-openassistant` — Instruction Data — Community Conversation Trees (OpenAssistant) [text/demonstration]
- `instruction-self-instruct` — Instruction Data — Synthetic Bootstrap (Self-Instruct / Alpaca) [text/demonstration]
- `judge-eval-study` — LLM-as-Judge Evaluation Study [text/rubric_rating]
- `ner-conll2003` — Expert Span Annotation for NER (CoNLL-2003) [text/extraction]
- `nli-snli-artifacts` — NLI Data by Crowd Hypothesis-Writing (SNLI) — the Artifacts Cautionary Tale [text/classification]
- `pointcloud-detection-nuscenes` — Multi-Sensor 3D Bounding-Box Annotation (nuScenes) [3d_pointcloud/structured_output]
- `pointcloud-segmentation-semantickitti` — Dense Point-Cloud Segmentation over Superimposed Scans (SemanticKITTI) [3d_pointcloud/structured_output]
- `preference-anthropic-hh` — Preference Collection — Anthropic HH-RLHF [text/preference_ranking]
- `preference-constitutional-cai` — Preference Collection — Anthropic Constitutional AI (RLAIF) [text/preference_ranking]
- `preference-llama2-rlhf` — Preference Collection — Meta Llama 2 RLHF [text/preference_ranking]
- `preference-sparrow` — Preference Collection — DeepMind Sparrow (Rule-Conditional) [text/preference_ranking]
- `redteam-adversarial-dialogue` — Crowdsourced Adversarial Red-Team Dialogue Collection [text/red_team]
- `redteam-automated-perez` — Red-Teaming — Automated (LM-Generated Attacks) [text/red_team]
- `redteam-external-gpt4` — Red-Teaming — External Domain-Expert Network [multimodal/red_team]
- `relevance-pooling-trec` — TREC-Style Relevance Judgments via Pooling [text/relevance]
- `search-msmarco` — Relevance + Answers from Real Query Logs (MS MARCO) [text/relevance]
- `self-training-noisy-student` — Self-Training / Pseudo-Labeling (Noisy Student) [image/classification]
- `speech-librispeech` — Speech Data by Forced Alignment to Existing Text (LibriSpeech) [audio/transcription_translation]
- `synthetic-textbooks-phi` — Model-Generated + Model-Filtered Training Data (phi / Textbooks) [text/freeform_generation]
- `synthetic-with-audit` — Model-Generated Labels with Human Audit [multimodal/classification]
- `tabular-weak-supervision-snorkel` — Weak Supervision via Labeling Functions (Snorkel) [tabular/classification]
- `text-preference-rlhf` — Pairwise Preference Collection for RLHF [text/preference_ranking]
- `text-relation-distant-supervision` — Distant Supervision for Relation Extraction (KB Alignment) [text/extraction]
- `video-action-kinetics` — Crowdsourced Video Action Verification (Kinetics) [video/classification]
- `video-something-something` — Crowd-Acted Templated Action Videos (Something-Something) [video/classification]

## Appendix B — every risk signature

- `confounded` — a spurious cue (length, source, tier) rides along with the real signal
- `unanchored` — no gold / ground truth to check labels against
- `self_affinity` — a model judge favors its own family's outputs
- `inflation` — the bar creeps up; everything starts passing
- `underpowered` — too few items/reps to support the claim
- `priming` — item order or position contaminates the label
- `sampling_frame` — the labeled set isn't representative of deployment
- `drift` — guidelines / acceptance bar move over the campaign
- `bottleneck` — one stage (adjudication, expert review) gates throughput
- `over_specification` — guidelines so rigid they break on edge cases
- `under_specification` — so loose competent annotators disagree (low IAA)
- `label_leakage` — the label is derivable from a feature it shouldn't be / eval contaminated by training
- `class_imbalance` — rare-but-important classes under-sampled
- `gaming` — annotators optimize the pay/quota, not quality (Goodhart)
