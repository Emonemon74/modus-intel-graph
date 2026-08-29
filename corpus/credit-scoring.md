# Credit scoring and decisioning — background note

Source: summary compiled from Wikipedia, "Credit score"
(https://en.wikipedia.org/wiki/Credit_score), text available under CC BY-SA 4.0.
Retrieved 2026-08-29. Condensed reference for the research corpus, not a verbatim copy.

## What a credit score is

A numerical expression, derived from analysis of a person's credit files, that
represents their creditworthiness. Lenders use it to make rapid, consistent
decisions on who qualifies for credit and on what terms (approval, interest rate,
credit limit). Mobile carriers, insurers, landlords and government agencies use
similar techniques.

## Scoring methodologies

- United States: FICO is the dominant model — proprietary algorithms over data from
  Equifax, Experian and TransUnion, scores 300-850. Income and employment history
  are NOT used by the bureaus in the score itself (though lenders weigh them
  separately).
- Statistical techniques in use elsewhere include logistic / non-linear probability
  modelling, MARS, CART, CHAID and random forests for scorecard development.
- India's CIBIL score is 300-900; Brazil's is 0-1000, expressing the chance a
  consumer profile pays bills on time over the next 12 months.
- Digital / online lenders increasingly use alternative data to score
  thin-file borrowers, expanding access but raising new fairness questions.

## Decisioning and underwriting

- US: FICO scores feed risk-based pricing; mortgages typically pull three bureau
  variants. Score flavours are product-specific (e.g. auto-enhanced vs
  bankcard-enhanced).
- UK: no universal consumer score — each lender scores applicants on its own
  criteria, and those algorithms are trade secrets, so a consumer cannot know in
  advance whether they will be accepted.
- Behavioural scoring extends beyond approval: setting credit limits on existing
  accounts and identifying revenue-generating customers (a shift from pure risk
  management to revenue optimisation).

## AI, alternative data and fairness

Machine learning plus alternative data promises more inclusive underwriting but
raises transparency and bias concerns; most methodologies are proprietary.
Regulatory protections vary:
- US: Fair Credit Reporting Act — bureaus must investigate disputes within 45 days;
  consumers denied credit/insurance due to their score are entitled to a free
  score. Lenders need not reveal the score they used or the minimum required.
- Austria: consumers must opt in to use of private data; annual access rights;
  incorrect data must be deleted. Germany: one free copy of all held data per year.

Scores are shown to be predictive of risk, but decentralised systems, proprietary
algorithms and limited transparency create persistent algorithmic-bias and
fair-lending challenges — heightened as alternative data and ML widen the inputs.
