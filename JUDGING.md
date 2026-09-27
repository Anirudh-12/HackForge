# Judging Normalization Method

## Why Normalization?
Different judges have different baselines when grading projects. A lenient judge might consistently assign scores of 4s and 5s, while a strict judge might assign 2s and 3s for projects of similar quality. Without normalization, projects assigned to the strict judge are systematically disadvantaged.

## Z-Score Normalization
To ensure fair comparisons, we apply **Z-score normalization**. This method evaluates each score relative to the distribution of scores provided by that specific judge.

### The Formula
For each track independently, we calculate the normalized score as follows:

1. **Calculate Raw Score**: For a given project, a judge's raw score is the weighted average of the criteria they evaluated.
   `Raw Score = Sum(Criterion Weight * Criterion Score) / Total Weight`

2. **Judge Statistics**: For each judge within a specific track, we collect all of their raw scores and compute their **Mean** and **Standard Deviation** (`stdev`).

3. **Calculate Z-Score**: Each raw score is converted to a Z-score, which represents how many standard deviations it is from that judge's mean.
   `Z = (Raw Score - Mean) / Stdev`

4. **Scale to 50-100 Range**: To make the scores intuitive (similar to a 0-100 scale), we map the Z-score using:
   `Normalized Score = 50 + (Z * 15)`
   This maps ±3 standard deviations to a readable range of approximately [5, 95].

5. **Final Project Score**: The final normalized score for a project is the average of its normalized scores from all judges who reviewed it.

## Edge Cases

- **Single Project in Track**: If a track only has one project, the standard deviation is 0. In this case, the normalized score defaults to 50.
- **Identical Scores**: If a judge gives every project the exact same score, their standard deviation is 0, which would result in division by zero. We handle this by setting their standard deviation contribution to 0 deviation (defaulting to a normalized score of 50).
- **Scope**: Normalization occurs **per track**, not globally. A project in the "Security" track is not compared to a project in the "Design" track, as they have different judge pools and competition dynamics.
