# Fuel & Spark Auto-Tuner

A single-page tool that corrects HP Tuners tables from VCM Scanner datalogs.

Open `index.html` in a browser (or use the hosted copy). Everything runs locally in the page; nothing is uploaded.

## What it tunes

| Table | Data it needs | What it does |
| --- | --- | --- |
| VE (RPM × MAP or airmass) | Wideband + commanded fuel (fuel trims optional) | Scales each cell by measured ÷ commanded lambda |
| MAF airflow vs frequency | Wideband + commanded fuel, MAF Hz | Same correction on the 1-D MAF curve |
| Spark advance | Knock retard | Pulls timing where knock showed up. It never adds timing. |

It can also take a pasted VCM Scanner histogram of fuel error % instead of a full log.

## How it works

1. In VCM Editor, right-click the table and choose **Copy with Axis**, then paste it in.
2. Export the log from VCM Scanner as CSV and drop it in. Channels are matched by name; check them in Step 3.
3. Samples are filtered (cold engine, quick throttle moves, decel fuel cut, out-of-range readings). The wideband is shifted to account for its delay, and each sample is spread over the 4 nearest cells.
4. Cells with enough samples are corrected, smoothed lightly, and limited to a max change per pass.
5. Paste the result back: click the top-left cell of the table body and press Ctrl+V, or use Paste Special → Multiply by % with the change table.

Repeat the log → correct → flash loop until the changes are small. Always check the result before flashing.
