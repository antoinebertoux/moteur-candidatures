# Scoring and calls to Claude

## Scoring

`moteur noter` gives each `a_noter` ad a score, a summary and two hints (letter
requested, language), in one short call to Claude per batch.

- **NOT-01** · `a_noter` ads are sent in batches of `taille_lot`, one call per batch,
  with the scoring model (Haiku by default).
- **NOT-02** · A failed batch (failed call, unreadable response) is reported and stays
  `a_noter`: it will be retried on the next run. The other batches carry on.
- **NOT-03** · For each ad, Claude receives only: identifier, company, title, location,
  salary label and the first 1,500 characters of the text.
- **NOT-04** · The system prompt holds the scoring instructions, the `profil` from
  `config.toml` and the past refusals of NOT-08, and nothing else (not the salary floor).
- **NOT-05** · Claude answers with a JSON array. For each entry: identifier copied back;
  score from 0 to 100; two-sentence summary in French (the role, then the strong or
  blocking point); `lettre_demandee` true only if the ad asks for a cover letter;
  language `en` if the ad is in English, otherwise `fr`. *(untested: instruction to the
  model; reading the response is checked by NOT-06)*
- **NOT-06** · Reading the response: an entry with an unknown identifier or a
  non-numeric score is ignored (the ad stays `a_noter`); the score is rounded and clamped
  between 0 and 100; the summary is cut at 400 characters; any language other than `en`
  means `fr`. A response that is not an array fails the batch.
- **NOT-08** · Past refusals: the 40 most recent `refusee` applications that have a reason
  other than `doublon` are listed in the system prompt (company, title, reason label and
  detail), with the instruction to lower the score of similar ads for the same reason.
  With no such refusal, the section is left out.
- **NOT-07** · The command prints the number of ads scored and the number still waiting.
  *(untested)*

## Calling Claude

- **CLA-01** · Claude is called through `claude -p` with User's subscription, never
  with an API key. Each call runs without tools, without MCP servers, without keeping a
  session, with the requested model and system prompt; the prompt goes through standard
  input and the output is read as JSON.
- **CLA-04** · Only two calls are allowed tools: the interview preparation (PREP-20), web
  search and page fetching; and the company link lookup (LNK-12), web search only.
  Nothing else.
- **CLA-02** · These are failures: `claude` not found, no answer within 10 minutes,
  non-zero exit code, non-JSON output, error reported by Claude, empty answer.
- **CLA-03** · In a response, the content of the first ` ``` ` block is used if there is
  one; JSON is found even when surrounded by text.
