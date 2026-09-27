# ⚖️ HackForge — Judging Engine & Normalization Proof

> **Mathematical proof, edge-case derivations, and Bradley-Terry pairwise modeling.**  
> *Addresses the Normalization Proof (Hard) and Pairwise Mode (Hard) bonus challenges.*

---

## 1. The Core Problem in Hackathon Evaluation

In any hackathon with more than ~10 projects, no single judge can review every submission. Projects are distributed across a panel of judges. This introduces severe systemic distortions:

1. **Calibration Disparity:** Lenient judges assign raw scores in the $[4.0, 5.0]$ range; harsh judges assign $[1.5, 3.0]$.
2. **Assignment Inequity:** A superior project evaluated exclusively by a harsh judge receives a lower raw average than a mediocre project evaluated by a lenient judge.
3. **Cognitive Scale Fatigue:** As judges review multiple projects, their internal threshold drifts. Numerical Likert scales (1–5) suffer low inter-rater reliability.

HackForge solves this through a dual-engine architecture:
- **Per-Track Z-Score Normalization** for rubric evaluations.
- **Bradley-Terry Pairwise ELO Estimation** for comparative judgments.

---

## 2. Rigorous Proof: Cross-Judge Z-Score Normalization

### 2.1 The Mathematical Model

Let $J$ be the set of judges and $P_t$ be the set of projects in track $t$.  
For each judge $j \in J$ who evaluated projects in track $t$, let:

$$S_{j,t} = \{ s_{1,j}, s_{2,j}, \dots, s_{N_j,j} \}$$

be the set of raw weighted scores assigned by judge $j$ to $N_j$ distinct projects in track $t$.

#### Step 1: Raw Weighted Criterion Score
For project $i$ evaluated by judge $j$ over $C$ criteria with weights $w_c$:

$$s_{i,j} = \frac{\sum_{c=1}^C w_c \cdot v_{i,j,c}}{\sum_{c=1}^C w_c}$$

where $v_{i,j,c} \in \{1, 2, 3, 4, 5\}$ is the score assigned to criterion $c$.

#### Step 2: Judge Distribution Parameters
We calculate the empirical mean $\mu_{j,t}$ and sample standard deviation $\sigma_{j,t}$:

$$\mu_{j,t} = \frac{1}{N_j} \sum_{i=1}^{N_j} s_{i,j}$$

$$\sigma_{j,t} = \sqrt{\frac{1}{N_j} \sum_{i=1}^{N_j} (s_{i,j} - \mu_{j,t})^2}$$

#### Step 3: Z-Score Standardization
The raw score is mapped to its standard deviation distance from that specific judge's mean:

$$z_{i,j} = \frac{s_{i,j} - \mu_{j,t}}{\sigma_{j,t}}$$

#### Step 4: Rescaling to Standardized Baseline $[0, 100]$
To provide organizers with intuitive, comparable numbers, we apply a linear transformation:

$$\text{Score}_{i,j}^{\text{norm}} = 50.0 + (15.0 \times z_{i,j})$$

- $\mathbf{\mu = 50.0}$: An exactly average project from that judge maps to $50.0$.
- $\mathbf{\text{Scale} = 15.0}$: Per Chebyshev's inequality and the empirical rule for normal distributions, $99.7\%$ of evaluations fall within $\pm 3\sigma \implies [5.0, 95.0]$.

#### Step 5: Multi-Judge Consensus Aggregation
The final normalized score for project $i$ across all assigned judges $J_i$ is:

$$\text{Score}_i^{\text{final}} = \frac{1}{|J_i|} \sum_{j \in J_i} \text{Score}_{i,j}^{\text{norm}}$$

---

### 2.2 Proof of Edge Cases & Divide-by-Zero Handling

Our implementation in `src/queries.py` mathematically handles every potential boundary condition:

#### Theorem 1: Identical Scores Assigned by a Judge ($\sigma = 0$)
*Condition:* Judge $j$ assigns the identical score $k$ to every project they review:
$$s_{1,j} = s_{2,j} = \dots = s_{N,j} = k$$

*Proof:*
$$\mu_{j,t} = \frac{1}{N} \sum_{i=1}^N k = k$$
$$\sigma_{j,t}^2 = \frac{1}{N} \sum_{i=1}^N (k - k)^2 = 0 \implies \sigma_{j,t} = 0$$

Direct evaluation of $z = \frac{k - k}{0}$ is an indeterminate form ($0/0$).  
*Resolution in `src/queries.py`:*
```python
if stdev == 0:
    norm = 50.0
else:
    z = (raw - mean) / stdev
    norm = 50.0 + (z * 15.0)
```
If a judge exhibits zero variance, they provide zero discriminating signal between projects. Setting $\text{Score}^{\text{norm}} = 50.0$ neutralizes their influence without corrupting the aggregate rankings.

#### Theorem 2: Single Submission Reviewed ($N = 1$)
*Condition:* A judge reviews exactly one project in a given track ($N=1$).  
*Proof:*
$$\mu_{j,t} = s_{1,j}$$
$$\sigma_{j,t} = \sqrt{\frac{1}{1} (s_{1,j} - s_{1,j})^2} = 0$$
By Theorem 1, $\sigma=0$, mapping safely to the neutral baseline of $50.0$.

#### Theorem 3: Conflict of Interest Exclusion
If a judge marks `conflict_of_interest = True` on project $i$:
$$S_{j,t} \leftarrow S_{j,t} \setminus \{s_{i,j}\}$$
The biased score is excised *prior* to computing $\mu_{j,t}$ and $\sigma_{j,t}$. The judge's distribution cannot be poisoned by their conflicted score.

---

## 3. Pairwise Mode: Bradley-Terry / ELO Rating Model

### 3.1 Cognitive Advantage of Pairwise Evaluation
Psychometric research indicates human evaluators demonstrate significantly higher consistency when performing binary comparisons (*"Is Project A better than Project B?"*) than when producing absolute numeric ratings on a scale.

### 3.2 Bradley-Terry Logistic Formulation
Let each project $i$ possess a latent quality rating $R_i$. The probability that project $A$ defeats project $B$ in a head-to-head comparison is modeled by the logistic sigmoid:

$$P(A > B) = \frac{1}{1 + 10^{(R_B - R_A) / 400}}$$

$$P(B > A) = 1 - P(A > B) = \frac{1}{1 + 10^{(R_A - R_B) / 400}}$$

### 3.3 Dynamic Rating Update
When judge $j$ submits a pairwise comparison recorded in `pairwise_comparisons`:
- Winner $W$ receives actual outcome $S_W = 1$
- Loser $L$ receives actual outcome $S_L = 0$

With rating baseline $R_0 = 1500.0$ and learning factor $K = 32$:

$$R'_W = R_W + K \cdot (1 - P(W > L))$$

$$R'_L = R_L + K \cdot (0 - P(L > W))$$

### 3.4 Convergence & Zero-Sum Conservation
Because $P(W > L) + P(L > W) = 1$:
$$\Delta R_W + \Delta R_L = K(1 - P(W > L)) + K(-P(L > W)) = K(1 - (P(W > L) + P(L > W))) = 0$$
Total rating points in the system are strictly conserved. Ratings dynamically converge toward the true underlying quality ranking as comparison volume increases.

---

## 4. Worked Numerical Example on Fixture Data

Consider two judges in Track 3 evaluating three projects:

- **Judge 1 (Harsh):** Scores: $P_1 = 3.0, P_2 = 2.0, P_3 = 1.0$
  $$\mu_1 = 2.0, \quad \sigma_1 = \sqrt{\frac{1^2 + 0^2 + (-1)^2}{3}} = \sqrt{0.667} \approx 0.816$$
  - $P_1$: $z = (3.0 - 2.0)/0.816 = +1.225 \implies \text{Norm} = 50 + 15(1.225) = \mathbf{68.37}$
  - $P_2$: $z = (2.0 - 2.0)/0.816 = 0 \implies \text{Norm} = 50 + 15(0) = \mathbf{50.00}$
  - $P_3$: $z = (1.0 - 2.0)/0.816 = -1.225 \implies \text{Norm} = 50 + 15(-1.225) = \mathbf{31.63}$

- **Judge 2 (Lenient):** Scores: $P_1 = 5.0, P_2 = 4.0, P_3 = 3.0$
  $$\mu_2 = 4.0, \quad \sigma_2 = 0.816$$
  - $P_1$: $z = (5.0 - 4.0)/0.816 = +1.225 \implies \text{Norm} = \mathbf{68.37}$
  - $P_2$: $z = (4.0 - 4.0)/0.816 = 0 \implies \text{Norm} = \mathbf{50.00}$
  - $P_3$: $z = (3.0 - 4.0)/0.816 = -1.225 \implies \text{Norm} = \mathbf{31.63}$

### Result:
Even though Judge 1 scored $P_1$ as `3.0` and Judge 2 scored $P_3$ as `3.0`, their normalized scores reflect reality:
- $P_1$ was the top project for both judges $\implies$ **68.37**
- $P_3$ was the bottom project for both judges $\implies$ **31.63**

The lenient judge's generous scores and the harsh judge's strict scores are completely neutralized.
