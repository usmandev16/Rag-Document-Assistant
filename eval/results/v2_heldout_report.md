# Held-out eval (v2) report

## Run record

- **System under test:** commit `473b6e76cdc504d113eff9008d42625b0f9b864a`, unchanged from start to end. Default
  config: hybrid search (BM25 + dense, 20 each, RRF), reranker off (`RERANK_TOP_K=0`), 3,000-token context budget.
  No prompt, retrieval setting, chunking or router code was changed before or during the run.
- **Models:** `openai/gpt-oss-120b` for answers, `openai/gpt-oss-20b` as judge (same as v1). Unanswerable questions
  are graded by the refusal check, as in v1.
- **Sessions:** 2, with 2 Groq API keys. Session 1 finished 58 questions and stopped at Groq's daily token limit;
  session 2 (`--retry-errors`) ran only the remaining 39. No question was run twice. About 359,000 tokens in total.
- **Documents:** 28 files (split from 12 source documents) in a fresh namespace: 7,385 chunks, of which 5,719 come
  from the two plant workbooks (all ~140,000 rows ingested, none dropped or sampled). 80 PDF pages went through
  the OCR fallback, 36 of them in `bidding-document_part1of5.pdf`. Per-file chunk counts and OCR'd page numbers:
  `v2_evidence_check.txt`.
- **Pre-run checks:** all 15 aggregation answers match an independent pandas calculation
  (`v2_aggregation_check.txt`). Evidence check: 56 of 72 evidence strings are in the ingested chunks. 4 evidence
  strings were updated to the text as ingested (q001, q018, q038, q056; listed in `v2_evidence_changes.json`).
  The other 16 are inside Word tables, which the loader does not ingest; their evidence was left unchanged.

## 1. Overall

| | v1 final (50 questions, 4 documents) | v2 held-out (97 questions, 28 files) |
|---|---|---|
| Answer accuracy | 92% (46/50) | 66% (64/97) |
| Retrieval hit rate | 83% (25/30) | 60% (43/72) |

Retrieval hit uses the v2 definition (evidence in a sent chunk from one of the question's source files, whitespace collapsed to single spaces). With the v1 script's own check (any sent chunk, all whitespace removed) it is 61% (44/72).

## 2. Breakdown

### By question type

| Type | Questions | Retrieval hit rate | Answer accuracy | Note |
|---|---|---|---|---|
| factual | 48 | 58% (28/48) | 52% (25/48) |  |
| table | 10 | 80% (8/10) | 70% (7/10) |  |
| paraphrased | 14 | 50% (7/14) | 64% (9/14) |  |
| aggregation | 15 | n/a | 93% (14/15) |  |
| unanswerable | 10 | n/a | 90% (9/10) |  |

### By tag

| Tag | Questions | Retrieval hit rate | Answer accuracy | Note |
|---|---|---|---|---|
| close_values | 1 | n/a | 100% (1/1) | too small to conclude |
| near_duplicate | 10 | 20% (2/10) | 20% (2/10) |  |
| prior_knowledge_trap | 5 | n/a | 100% (5/5) | too small to conclude |
| roman_urdu | 5 | 40% (2/5) | 40% (2/5) | too small to conclude |

### By source file

A question with several source files is counted under each of them. Unanswerable questions have no source file.

| Source file | Questions | Retrieval hit rate | Answer accuracy | Note |
|---|---|---|---|---|
| 2026261223723116BiddingDocumentforSolar_part1of4.pdf | 3 | 100% (3/3) | 67% (2/3) | too small to conclude |
| 2026261223723116BiddingDocumentforSolar_part2of4.pdf | 3 | 0% (0/3) | 33% (1/3) | too small to conclude |
| 2026261223723116BiddingDocumentforSolar_part4of4.pdf | 3 | 0% (0/3) | 33% (1/3) | too small to conclude |
| Draft-Model-Bidding-Documents-on-Lease-Purchase-Model_part1of3.docx | 3 | 33% (1/3) | 33% (1/3) | too small to conclude |
| Draft-Model-Bidding-Documents-on-Lease-Purchase-Model_part3of3.docx | 3 | 33% (1/3) | 33% (1/3) | too small to conclude |
| Draft-Model-Bidding-Documents-on-Own-Cost-Model_part1of2.docx | 2 | 0% (0/2) | 0% (0/2) | too small to conclude |
| Draft-Model-Bidding-Documents-on-Own-Cost-Model_part2of2.docx | 5 | 20% (1/5) | 20% (1/5) | too small to conclude |
| NetMeteringReferenceGuideforDISCOs150118-1_part1of2.pdf | 6 | 100% (6/6) | 100% (6/6) | too small to conclude |
| NetMeteringReferenceGuideforDISCOs150118-1_part2of2.pdf | 14 | 79% (11/14) | 79% (11/14) |  |
| Notification_Amendment_Prosumer_Regs-Final.pdf | 2 | 100% (2/2) | 100% (2/2) | too small to conclude |
| Pakistan_Energy_Indicators.xlsx | 4 | n/a | 75% (3/4) | too small to conclude |
| Plant_1_Solar_Data.xlsx | 6 | n/a | 100% (6/6) | too small to conclude |
| Plant_2_Solar_Data.xlsx | 5 | n/a | 100% (5/5) | too small to conclude |
| SRO-892-Sep-2015_part1of2.pdf | 13 | 62% (8/13) | 69% (9/13) |  |
| SRO-892-Sep-2015_part2of2.pdf | 3 | 67% (2/3) | 100% (3/3) | too small to conclude |
| Tender_Documents_of_Solar_Power_System_part1of2.docx | 11 | 82% (9/11) | 73% (8/11) |  |
| Tender_Documents_of_Solar_Power_System_part2of2.docx | 1 | 100% (1/1) | 100% (1/1) | too small to conclude |
| bidding-document_part1of5.pdf | 4 | 100% (4/4) | 75% (3/4) | too small to conclude |
| bidding-document_part2of5.pdf | 2 | 50% (1/2) | 100% (2/2) | too small to conclude |
| tender_tender-document-file_20260513131133_part1of4.docx | 10 | 10% (1/10) | 10% (1/10) |  |
| tender_tender-document-file_20260513131133_part2of4.docx | 2 | 100% (2/2) | 50% (1/2) | too small to conclude |
| tender_tender-document-file_20260513131133_part4of4.docx | 3 | 67% (2/3) | 33% (1/3) | too small to conclude |

### By source document (parts combined)

| Source document | Questions | Retrieval hit rate | Answer accuracy | Note |
|---|---|---|---|---|
| 2026261223723116BiddingDocumentforSolar | 6 | 50% (3/6) | 50% (3/6) | too small to conclude |
| Draft-Model-Bidding-Documents-on-Lease-Purchase-Model | 6 | 33% (2/6) | 33% (2/6) | too small to conclude |
| Draft-Model-Bidding-Documents-on-Own-Cost-Model | 7 | 14% (1/7) | 14% (1/7) | too small to conclude |
| NetMeteringReferenceGuideforDISCOs150118-1 | 20 | 85% (17/20) | 85% (17/20) |  |
| Notification_Amendment_Prosumer_Regs-Final | 2 | 100% (2/2) | 100% (2/2) | too small to conclude |
| Pakistan_Energy_Indicators | 4 | n/a | 75% (3/4) | too small to conclude |
| Plant_1_Solar_Data | 6 | n/a | 100% (6/6) | too small to conclude |
| Plant_2_Solar_Data | 5 | n/a | 100% (5/5) | too small to conclude |
| SRO-892-Sep-2015 | 14 | 64% (9/14) | 71% (10/14) |  |
| Tender_Documents_of_Solar_Power_System | 11 | 82% (9/11) | 73% (8/11) |  |
| bidding-document | 6 | 83% (5/6) | 83% (5/6) | too small to conclude |
| tender_tender-document-file_20260513131133 | 12 | 25% (3/12) | 17% (2/12) |  |

## 3. Latency and request size

- Retrieval latency (retrieval-only run, 72 questions, no LLM): p50 306 ms, p95 333 ms, max 475 ms.
- Largest request: 6823 tokens (q088); median 3662 tokens.

## 4. Failed questions (33)

| ID | Type | Question | Expected | System answer | Category | Note |
|---|---|---|---|---|---|---|
| q001 | factual | What is the bid security amount for the State Life solar tender in Sukkur? | Rs. 150,000, as a pay order or bank draft in favour of State Life Insurance Corporation of Pakistan. | The bid security amount is Rs 150,000/‑[1][2] | `generation_error` | Right chunk sent; gives the amount but not the form (pay order / bank draft). |
| q002 | factual | By what date and time must bids for the State Life Sukkur 30 kW solar system be submitted? | On or before 04-06-2026 at 11:00 AM, through E-PADS. | I don't know. | `retrieval_miss` | Evidence chunk was candidate 20 of 34; only the top 15 fit the token budget. |
| q003 | factual | What is the defect liability period in the State Life Sukkur solar tender? | 12 months from the date of completion of the project, including net metering. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q004 | factual | How long must tenders remain valid for the State Life Sukkur project? | 120 days from the date of opening of the bid. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q005 | factual | What minimum third party insurance does the State Life Sukkur tender require? | Rs. 500,000 minimum for any one incident of loss of property or life. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q006 | factual | How many solar modules are listed in the State Life Sukkur bill of quantities, and what wattage range? | 56 modules of 610W to 625W (Tier-1, Grade-A, N-type). | The bill of quantities lists 86 solar modules, each specified with a wattage between 580 W and 600 W[1]. | `wrong_document` | Fact is only in a Word table, which the loader does not ingest. Answered from the FBR bidding document instead. |
| q007 | factual | Which inverter brands are named in the State Life Sukkur bill of quantities? | Sungrow, Huawei or SMA (or equivalent). | The bill of quantities lists the following inverter manufacturers: Goodwe, Sineng, Huawei, Nitrox and Fronus (or an equivalent approved by the Employer/Engineer)[1]. | `wrong_document` | Fact is only in a Word table, which the loader does not ingest. Answered from the COMSATS bidding document instead. |
| q009 | factual | What solar panel warranty does the State Life Sukkur tender ask for? | 16-year product warranty and 30-year performance warranty, plus a 5-year inverter warranty and a one-year warranty on the complete project. | The tender requires a solar‑panel product warranty of 16 years and a performance warranty of 30 years[1]. | `generation_error` | Right chunk sent; gives the panel warranties but leaves out the inverter and project warranties. |
| q011 | factual | In which currency must bids be submitted for the FBISE 300 kWp solar tender? | In US Dollars, converted to Pakistani Rupees at the bank exchange rate when the contract is signed. | Bids must be submitted in US Dollar[1] | `retrieval_miss` | Evidence chunk was candidate 14 of 36; 13 were sent. Partial answer (currency only) from another part. |
| q014 | factual | Within how many weeks must the FBISE solar system be completed after contract signing? | No more than 12 weeks from signing, not counting net metering time. | I don't know. | `retrieval_miss` | Evidence chunk was not among the 33 retrieved candidates. |
| q018 | factual | When was the pre-bid meeting for the FBR solar tender held? | 9 February 2026 at 2:30 PM, in Room 358, 3rd Floor, FBR House, Islamabad. | The pre‑bid meeting for the Federal Board of Revenue solar tender was held on 9 February 2026. [1][2] | `generation_error` | Right chunk sent; gives the date but not the time and room. |
| q021 | factual | What penalty applies if the FBR solar system is delivered late? | 0.1% per day after 90 days, up to a maximum of 10%. | If the solar system is delivered late, the Procuring Agency may impose liquidated damages under GCC Clause 26, at its discretion, when it decides to extend the supplier’s time for performance [1][2]. | `retrieval_miss` | Evidence chunk was candidate 35 of 37; 14 were sent. Answered generally from other clauses. |
| q023 | factual | What is the deadline for e-bids in the COMSATS Attock 400 kW solar procurement? | Tuesday, September 15, 2026 at 02:00 PM, through EPADS v2.0. | The e‑bid deadline is Tuesday, September 15, 2026 at 02:00 PM.[1] | `generation_error` | Right chunk sent; date and time are right, but 'through EPADS v2.0' is missing. |
| q029 | factual | What is the maximum fine for violating the 2015 net metering regulations? | A fine of up to 100 million rupees. | I don't know. | `retrieval_miss` | Evidence chunk was candidate 28 of 33; 15 were sent. |
| q034 | factual | What earthing resistance does the AEDB net metering guide allow for the solar PV support structure? | Total earth resistance not exceeding 5 ohms, using at least two separate interconnected earth electrodes. | The guide permits a total earth resistance of up to 5 ohms for the solar PV support structure [1]. | `generation_error` | Right chunk sent; gives 5 ohms but not the two-electrode requirement. |
| q041 | factual | In the PPIB Own Cost Model bidding documents, what is the bid validity period? | 90 days from the date of bid opening. | The bid must remain valid for ninety (90) days from the date fixed for the bid submission deadline[1]. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. Found '90 days' in another clause of the same document, with a different start point. |
| q042 | factual | In the PPIB Lease Purchase Model bidding documents, what is the bid validity period? | 60 days after the date of bid opening. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q043 | factual | How much bid security per kW does the Own Cost Model require? | Rs. 9,000 per kW. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q044 | factual | How much bid security per kW does the Lease Purchase Model require? | Rs. 7,000 per kW. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q046 | factual | What minimum experience does the Own Cost Model require from bidders? | Net-metering solar projects completed in the last two years with cumulative capacity of 250 kW or above. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q047 | factual | What minimum average annual turnover does the Lease Purchase Model require? | PKR 25 million over the last two years. | The Lease Purchase Model requires a minimum average annual turnover of PKR 100 million in the last three years[1]. | `wrong_document` | Fact is only in a Word table, which the loader does not ingest. Answered from the COMSATS bidding document instead (PKR 100 million). |
| q048 | factual | What is the liquidated damages rate in the Own Cost Model contract? | 0.33% of the contract price for every day of delay. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q049 | factual | Under the 2015 regulations themselves, how many working days does the DISCO have to acknowledge a net metering application? | Five working days. | I don't know. | `wrong_document` | 12 of 15 sent chunks came from the AEDB guide, not the 2015 regulations; the right chunk was candidate 34 of 34. |
| q051 | table | How much roof area is available on Roof-3 at FBISE, and how many kWp of modules can it hold? | 5,600 sq ft, for 60 kWp. | I don't know. | `false_refusal` | The roof-area table chunk was sent, but the system said it doesn't know. |
| q058 | table | What is the minimum payment per bill in the State Life Sukkur contract? | Not less than Rs. 1,500,000 per bill. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q059 | table | What are the payment percentages in the Own Cost Model contract? | 20% advance (against an advance payment guarantee), 55% on delivery of equipment to site, 25% on issue of the Taking Over Certificate. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. |
| q063 | paraphrased | If I plan to make my solar system bigger after it's connected, how much notice do I owe the DISCO? | At least forty working days of advance notice, with a revised application. | I don't know. | `retrieval_miss` | Evidence chunk was not among the 37 retrieved candidates. |
| q068 | paraphrased | How efficient do inverters need to be under the PPIB model documents? | CEC efficiency of at least 98.5%, three-phase grid-tied, IP65, THD under 3%. | The inverter must have a CEC efficiency of not less than 98.5 %[1] | `generation_error` | Right chunk sent; gives the efficiency but not phase, IP rating or THD. |
| q071 | paraphrased | net metering ka agreement kitne saal ke liye hota hai? | Three years from commissioning, renewable for further three-year terms. | I don't know. | `retrieval_miss` | Roman Urdu question; evidence chunk not in the top 100 of either search. |
| q072 | paraphrased | State Life Sukkur wale tender mein late kaam par kitna jurmana hai? | 0.1% per day, up to a maximum of 10% of the awarded sum. | I don't know. | `retrieval_miss` | Fact is only in a Word table, which the loader does not ingest. (Roman Urdu question.) |
| q075 | paraphrased | FBR wale solar ki delivery kitne din mein karni hai? | Within 90 days of contract signing or purchase order. | I don't know. | `retrieval_miss` | Roman Urdu question; evidence chunk was not among the 33 retrieved candidates. |
| q090 | aggregation | What is the highest share of electricity from hydroelectric sources in the indicators file? | about 60.14% (in 1978) | The highest share of electricity from hydroelectric sources is 840000000.0, according to the file [1]. | `generation_error` | Spreadsheet path: the plan filtered 'Indicator Name contains hydroelectric', which matched several indicators (135 rows, including kWh totals), so max(Value) was 840,000,000. |
| q100 | unanswerable | What tilt angle is specified for the mounting structure in the COMSATS Attock tender? | The documents don't contain this information. | The tender specifies that the mounting‑structure tilt angle must be at least 26 degrees[1]. | `hallucination` | Gave a 26-degree tilt angle taken from the FBISE tender, a different document. |

Failures by category: `retrieval_miss` 20, `generation_error` 7, `wrong_document` 4, `false_refusal` 1, `hallucination` 1.

No failure was a `router_misroute`. Three aggregation questions (q087, q088, q089) did go down the documents path instead of the spreadsheet path, and were answered correctly from retrieved chunks; q089's average was worked out by the LLM, which the prompt forbids, so that result is not dependable.

## 5. The three biggest problems

### 1. Word tables are not ingested: 15 questions

Questions: q003, q004, q005, q006, q007, q041, q042, q043, q044, q046, q047, q048, q058, q059, q072.

The Word loader reads `document.paragraphs` only (`backend/src/loaders.py`), so everything inside a table is dropped at ingestion. In these tender documents the tables hold the key terms: bid security, validity, bill of quantities, payment terms. 16 questions asked for facts that exist only in tables; 15 failed (one was answered from a paragraph that says the same thing). Three of the 15 were answered confidently from a different tender, which is worse than saying "I don't know".

**Suggested fix:** read tables as well as paragraphs, in document order, rendering each row as "header: value" text the way spreadsheet rows are handled. Re-ingest and re-run these questions.

### 2. The right chunk is retrieved but cut, or not retrieved: 9 questions

Questions: q002, q011, q014, q021, q029, q049, q063, q071, q075.

The evidence was ingested, but did not reach the LLM. For 5 of them (q002, q011, q021, q029, q049) the right chunk was among the 33 to 37 retrieved candidates, but ranked below the 13 to 15 that fit the 3,000-token budget (`v2_miss_ranks.json`). For the other 4 (q014, q063, q071, q075) it was not among the candidates at all; two of those are Roman Urdu questions, which share no words with the English text and are poorly served by the English embedding model. q049 is the near-duplicate case: 12 of the 15 chunks sent came from the AEDB guide, not the 2015 regulations the question names.

**Suggested fix:** rerank the retrieved candidates before applying the token budget (the cross-encoder exists but is off because it takes about 2.5 s on CPU; a faster reranker or a GPU would be needed). For Roman Urdu, rewrite the question into English before retrieval. For near-duplicates, detect the document named in the question and filter or boost by source file.

### 3. Incomplete answers: 6 questions

Questions: q001, q009, q018, q023, q034, q068.

The right chunk was sent and the answer is correct as far as it goes, but it leaves out part of the expected answer (for example the amount without the form of payment, or the date without the time and place), and the judge marks it wrong. Some of the expected answers include details the question did not ask for, so part of this is judge strictness, as in v1.

**Suggested fix:** tell the model to include the conditions and qualifiers stated with a fact (form, time, place, limits), and separately consider grading partial answers as partially correct.

### Smaller problems

- **False refusal (q051):** the table chunk with the roof areas was sent, but the system said it doesn't know.
- **Wrong spreadsheet plan (q090):** a `contains` filter on the indicator name matched several indicators. Filtering on the indicator code, or checking that a filter leaves one indicator, would avoid it.
- **Hallucination (q100):** an unanswerable question about one tender was answered with a value from another tender. The other 9 unanswerable questions were correctly refused.

