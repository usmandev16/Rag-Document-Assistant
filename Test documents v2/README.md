# Test documents v2

The 28 files used by the held-out eval (`eval/dataset_v2.jsonl`, results in `eval/results/v2_heldout_report.md`).

They come from 12 source documents. The 8 large PDF and Word documents were split into parts (for example `bidding-document_part2of5.pdf`); the 3 spreadsheets and the one-page notification are whole.

| Source document | Files | Type |
|---|---|---|
| `2026261223723116BiddingDocumentforSolar` (FBR solar bidding document) | 4 parts | PDF |
| `bidding-document` (COMSATS Attock solar bidding document) | 5 parts | PDF |
| `NetMeteringReferenceGuideforDISCOs150118-1` (AEDB net metering guide) | 2 parts | PDF |
| `SRO-892-Sep-2015` (2015 net metering regulations) | 2 parts | PDF |
| `Notification_Amendment_Prosumer_Regs-Final` | 1 | PDF |
| `Draft-Model-Bidding-Documents-on-Own-Cost-Model` | 2 parts | Word |
| `Draft-Model-Bidding-Documents-on-Lease-Purchase-Model` | 3 parts | Word |
| `Tender_Documents_of_Solar_Power_System` (FBISE tender) | 2 parts | Word |
| `tender_tender-document-file_20260513131133` (State Life Sukkur tender) | 4 parts | Word |
| `Plant_1_Solar_Data.xlsx` (sheets `Generation`, `Weather`) | 1 | Excel |
| `Plant_2_Solar_Data.xlsx` (sheets `Generation`, `Weather`) | 1 | Excel |
| `Pakistan_Energy_Indicators.xlsx` (sheet `Indicators`) | 1 | Excel |

Six parts have no questions on purpose and act as distractors: `2026261223723116BiddingDocumentforSolar_part3of4.pdf`, `Draft-Model-Bidding-Documents-on-Lease-Purchase-Model_part2of3.docx`, `bidding-document_part3of5.pdf`, `bidding-document_part4of5.pdf`, `bidding-document_part5of5.pdf` and `tender_tender-document-file_20260513131133_part3of4.docx`.

The three spreadsheets were converted from CSV. Plant 1's `DATE_TIME` uses `15-05-2020 00:00` format and Plant 2's uses ISO format; this difference is part of the test.

The original download source of each document is not recorded here.
