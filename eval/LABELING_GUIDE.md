# Labeling Guide

Write your own definitions below before you start labeling, and keep them the same for all
1,020 passages. Judge each passage on its own: does *this passage* answer the question for the
member it describes?

## 2 = Relevant

What makes a passage fully answer the question?

- **Direct factual confirmation**: The passage explicitly states or confirms that the described member satisfies the query (e.g. held the specific leadership post, earned the specific medal, graduated from the specific institution, or has the described life experience).
- **Meets any active metadata filter**: For filtered queries, the member and passage adhere to the specified constraints (e.g. chamber, party, or state).
- **Historical inclusion**: For career and biographical queries (e.g., "served as mayor", "state attorney general", "former prosecutor"), service at any point in the member's career qualifies as relevant.

## 1 = Partly relevant

What makes a passage related but not a full answer?

- **Subordinate / Adjacent roles**: The member held a related but distinct or lesser title (e.g. committee member or ranking member instead of chair; deputy/assistant whip instead of majority whip; speaker pro tempore or candidate instead of Speaker).
- **Family / Background connection**: The topic relates to family members or relatives rather than the member themselves (e.g. parents immigrated when asking about the member immigrating, or uncle was a reporter).
- **Topical overlap without personal fulfillment**: The passage discusses legislation, resolutions, or court cases on the topic, but does not confirm the member's personal background (e.g. sponsored veterans' bill but passage doesn't confirm personal military service).
- **Chamber / Jurisdictional mismatch**: Related position in a state legislature when a federal congressional role is clearly requested, or House member when the query specifically targets Senators (e.g., c05).

## 0 = Not relevant

What makes a passage not count, even if it shares words with the question?

- **Incidental keyword overlap**: Words from the query appear in unrelated contexts (e.g. "Eagle Transfer Station" for "Eagle Scout", "Ed Pastor" or "Dan Pastore" for "pastors", calling for a "special prosecutor" for "former prosecutor").
- **Unrelated committee lists or generic actions**: Rote lists of committees or routine votes where the target query concept is absent.
- **Actions by others**: The passage describes another person who holds the title or committed the act (e.g. Pelosi calling for Duncan Hunter's resignation on campaign finance misuse).

## Edge cases I decided

Write down any rule you make while labeling (for example, how to treat committee lists or a
passage about someone else), so later questions are judged the same way.

- **Committee Chairs (`k01`)**: Full committee Chair = 2. Ranking Member or Vice Chair = 1. Regular committee member = 1. Unrelated committee = 0.
- **Leadership / Whips (`k02`, `k03`, `k04`, `k05`)**: Actual officeholder = 2. Official nominee / candidate or deputy/assistant whip = 1. State legislative equivalent = 1 or 0 (distractor).
- **Immigration (`c03`, `c14`, `f05`)**: Member personally immigrated / born abroad = 2. Parents/grandparents immigrated = 1 for personal queries, 2 for `c14` ("parents immigrated"). General immigration policy speeches = 0.
- **Military & Awards (`k09`, `k12`, `k14`, `k18`, `c08`, `f02`, `f10`)**: Direct award or service confirmed = 2. Attended academy without graduating = 1. Legislative advocacy for veterans without personal service confirmed in snippet = 1 or 0.
- **Campaign Money (`c20`)**: Member investigated/indicted/fined for campaign finance violations or personal misuse = 2. Coordination / technical grey-area = 1. Accusation against an opponent or other official = 0.

