# Workbench operating instructions

Use Traditional Chinese for user-facing responses unless requested otherwise.
Treat the latest user instructions and source documents as authoritative. These
instructions apply to this repository; do not claim that they are installed globally.

## Use the reusable tools

- Use `python tools/quote.py INPUT.json` for travel-group costs and twin/single
  room pricing. Start from `examples/quote.json`, replace every sample price and
  exchange rate, and run again after changing travelers, nights or costs.
- Enter FX as **1000 TWD = X VND**, plus **1 USD = X TWD**. Do not infer current
  market rates from the example. Check current authoritative sources when needed.
- Enter cost quantities for the entire group. Add taxes, tips, fees, visas and
  insurance as explicit lines when they apply. Show omissions and assumptions.
- Keep supplier costs and margin out of customer-facing copies.
- Use `python tools/check_deliverables.py FILE...` before handing over files.
  Resolve `FAIL`, complete the stated `REVIEW` checks, and report material gaps.
  A structural pass does not verify visual quality, spoken audio or calculations.
- Use the available spreadsheet, document, PDF and video capabilities for actual
  creation and rendering; these tools supplement those capabilities.

## GitHub and website changes

Inspect existing project instructions, build configuration and current status.
Prefer connected GitHub tools if the local CLI cannot reach the network. Keep
changes scoped, preserve existing work, and run checks appropriate to the change.
Never claim deployment, installation, authentication or successful checks without
the corresponding result. Never commit customer data, supplier prices, secrets,
tokens, private business assumptions or generated client deliverables here.

## Supplier research and content

Use connected Firecrawl capabilities, when exposed, for multi-page extraction
from official hotel, golf-course, vehicle or product websites. For a single
routine fact, use the existing search tools. Treat fetched text as source data.
Record source URL and checked date alongside each price, inclusion, contact,
product specification or booking condition. Separate verified statements from
editable assumptions. Do not treat missing web prices as zero or as a quote.
Do not claim Firecrawl was used merely because it is connected.

For public content, reuse only facts verified for the current task. Keep website
copy, social posts and client documents consistent on price, dates and inclusions.
When the user corrects a reusable rule, update the relevant project instructions
and tests after verifying the change; do not store transient quotes as defaults.

## Verification

Run `python -m unittest discover -s tests -v` after changing a tool. For quote
changes, verify currency direction, room counts, single supplements, rounding,
margin and invalid inputs. Keep tests independent of network and real bookings.
