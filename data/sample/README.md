# Sample data

**`illustrative-daily-prices.csv` is made up.** It is a formula (a slow rise, a wave and one sharp drop) written
out as one closing price per weekday from October 1, 2024 to September 30, 2026, under the placeholder symbol
`INDEX`. It is not the price history of any real fund. Holidays are not removed. Use it to learn the code; use
real data only from a source whose terms you have read.

Your own files (real prices, statements, journals) go in `data/private/`, which git ignores.

**`plan.toml` and `journal.csv`** are a sample plan for the `index-dca` method and a made-up year of trades
that breaks the plan on purpose (a skipped month, a late buy, a sale, a bigger buy and a buy of something else),
so `invest-witus review` has something to report.
