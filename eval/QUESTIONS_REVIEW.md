# Test Questions: Review of the Proposed Final Set (2026-10-17)

Status: **approved by Juan on 2026-10-17 and pooled (1,020 passages).** `eval/queries.csv` holds the set (notes = `final (approved 2026-10-17)`;
changed rows also say what changed). The original drafts are saved in `eval/queries_draft_2026-10-17.csv`.
Label in `eval/judgments.xlsx`; see `eval/LABELING_GUIDE.md`.

## What was checked

- **Real answers in the corpus:** each question's hybrid top 10 was read, and weak questions (where the real answer is
  missing from the corpus or the top 10, or there is only one real answer) were replaced.
- **No question built for one method:** relevant-looking passages appear in the hybrid top 10, and questions were not
  tuned to make any method win. How much BM25 and dense agree (passages in both top 10s) differs by group as expected:
  keyword 3.4 of 10 on average, conceptual 1.4, filtered 2.6.
- **Spread of answers:** "Members" is the number of different members in the hybrid top 10 (average: keyword 8.8, conceptual 9.1, filtered 7.7). Questions where one member filled most of the list were replaced.
- **No near-duplicates:** "filibuster reform" (same answers as the 60-vote-rule question) and "farmer" (same as the
  family-farm question) were replaced.
- **Wording:** factual and neutral (careers, roles, backgrounds, recorded actions).
- **Filter selectivity, broad to narrow:** party ≈ 48–50% of passages, chamber ≈ 33–34%, state 2–9%.

c05 ("senators who worked on Iraq bills") is Juan's own search from the app; c06 (family farm) matches another of his searches ("grow up on farm").

## All 50 questions

| ID | Group | Question | Filter | Passages matching filter | Members in hybrid top 10 | BM25 ∩ dense (top 10) | Change |
|---|---|---|---|---|---|---|---|
| k01 | keyword | chair of the House Armed Services Committee | – | all (18,434) | 10 | 2 | reworded: Senate -> House; the corpus has no passage naming the Senate committee's chair |
| k02 | keyword | Speaker of the House | – | all (18,434) | 8 | 5 | – |
| k03 | keyword | Senate Majority Leader | – | all (18,434) | 8 | 1 | – |
| k04 | keyword | House Majority Whip | – | all (18,434) | 7 | 4 | – |
| k05 | keyword | president pro tempore of the Senate | – | all (18,434) | 7 | 2 | – |
| k06 | keyword | impeachment manager | – | all (18,434) | 7 | 6 | – |
| k07 | keyword | Congressional Progressive Caucus | – | all (18,434) | 10 | 5 | – |
| k08 | keyword | Freedom Caucus founding member | – | all (18,434) | 10 | 1 | – |
| k09 | keyword | West Point graduate | – | all (18,434) | 10 | 5 | replaced 'chair of the House Oversight Committee' (no method found the chair) |
| k10 | keyword | Eagle Scout | – | all (18,434) | 9 | 4 | replaced 'chair of the Congressional Black Caucus' (top 10 were caucus lists, not chairs) |
| k11 | keyword | Rhodes Scholar | – | all (18,434) | 10 | 1 | – |
| k12 | keyword | Navy SEAL | – | all (18,434) | 8 | 5 | – |
| k13 | keyword | served as mayor | – | all (18,434) | 8 | 1 | replaced 'NASA astronaut' (answers were almost all Mark Kelly) |
| k14 | keyword | awarded the Bronze Star | – | all (18,434) | 10 | 4 | – |
| k15 | keyword | state attorney general | – | all (18,434) | 8 | 2 | – |
| k16 | keyword | House Ways and Means Committee | – | all (18,434) | 10 | 7 | – |
| k17 | keyword | Select Committee on the January 6 Attack | – | all (18,434) | 8 | 3 | – |
| k18 | keyword | Purple Heart | – | all (18,434) | 8 | 3 | replaced 'filibuster reform' (near-duplicate of c18) |
| k19 | keyword | voted to override the veto | – | all (18,434) | 10 | 6 | – |
| k20 | keyword | redistricting lawsuit | – | all (18,434) | 9 | 2 | – |
| c01 | conceptual | members who were teachers before entering politics | – | all (18,434) | 10 | 1 | – |
| c02 | conceptual | grew up poor | – | all (18,434) | 8 | 0 | – |
| c03 | conceptual | born outside the United States | – | all (18,434) | 10 | 1 | reworded from 'members born in another country' (more real answers) |
| c04 | conceptual | had a medical career before Congress | – | all (18,434) | 9 | 1 | – |
| c05 | conceptual | senators who worked on Iraq bills | – | all (18,434) | 8 | 1 | replaced 'former professional athletes' (few answers) with Juan's own logged search |
| c06 | conceptual | grew up working on a family farm or ranch | – | all (18,434) | 10 | 2 | – |
| c07 | conceptual | survived a cancer diagnosis | – | all (18,434) | 10 | 6 | – |
| c08 | conceptual | flew combat aircraft in the military | – | all (18,434) | 8 | 4 | – |
| c09 | conceptual | former television news reporters | – | all (18,434) | 8 | 2 | – |
| c10 | conceptual | politicians who switched political parties | – | all (18,434) | 8 | 1 | – |
| c11 | conceptual | first in their family to graduate from college | – | all (18,434) | 10 | 1 | reworded from '...to go to college' (finds more real answers) |
| c12 | conceptual | founded a business before running for office | – | all (18,434) | 10 | 0 | – |
| c13 | conceptual | worked in law enforcement before Congress | – | all (18,434) | 8 | 0 | – |
| c14 | conceptual | parents immigrated to the United States | – | all (18,434) | 10 | 0 | – |
| c15 | conceptual | pastors and ministers in Congress | – | all (18,434) | 7 | 3 | – |
| c16 | conceptual | trained as scientists or engineers | – | all (18,434) | 9 | 1 | – |
| c17 | conceptual | objected to certifying the 2020 presidential election results | – | all (18,434) | 10 | 2 | – |
| c18 | conceptual | wants to get rid of the Senate's 60-vote rule | – | all (18,434) | 10 | 0 | – |
| c19 | conceptual | fought against partisan district maps | – | all (18,434) | 9 | 3 | – |
| c20 | conceptual | accused of misusing campaign money | – | all (18,434) | 10 | 0 | – |
| f01 | filtered | former prosecutor | state=CA | 1,654 | 6 | 3 | – |
| f02 | filtered | served in the military | chamber=Senate | 6,214 | 6 | 4 | – |
| f03 | filtered | small business owner | chamber=House, party=Republican | 6,011 | 9 | 4 | replaced 'farmer' (near-duplicate of c06) |
| f04 | filtered | former judge | state=TX | 1,189 | 6 | 4 | replaced 'former teacher' TX (only one real answer) |
| f05 | filtered | immigrated to the United States | party=Democratic | 8,939 | 10 | 0 | – |
| f06 | filtered | former governor | chamber=Senate | 6,214 | 9 | 2 | – |
| f07 | filtered | physician | party=Republican | 9,259 | 8 | 2 | – |
| f08 | filtered | speaker of the state house | state=FL | 1,191 | 5 | 5 | – |
| f09 | filtered | served in the state legislature | state=NY | 1,071 | 10 | 0 | replaced 'former mayor' NY (only one real answer) |
| f10 | filtered | military veteran | state=AZ | 420 | 8 | 2 | reworded from 'Marine Corps veteran' AZ (answers were almost all Gallego) |

Changed: 12 of 50 (5 keyword, 3 conceptual, 4 filtered). Split stays 20 keyword / 20 conceptual / 10 filtered.

Expected judging load: about 21 pooled passages per question (union of the three methods' top 10s), so about 1,050 labels.
