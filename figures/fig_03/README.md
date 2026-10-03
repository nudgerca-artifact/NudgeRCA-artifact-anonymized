# Fig. 3: Two failed trajectories of Qwen3-4B

The two excerpts are copied verbatim from the two trajectory files in `data/trajectories/` (copies of the Section 3.2 trajectory set in
`../common/section3/data/bank_trajectories/trajectories/`):

- (a) `openrca_bank_1616667180_107__sc7.json`: ground truth IG02, answer Tomcat01 (trajectory 7)
- (b) `openrca_bank_1614866400_50__sc5.json`: ground truth MG01, answer Tomcat01 (trajectory 5)

`select.py` scans the full Section 3.2 trajectory set and lists the candidate trajectories from the adjudicated judgments of `../section_3/behavior_judge/` into
`data/candidates.json`. `render_excerpt.py <job>` writes the paragraphs of one trajectory to `data/excerpt_<job>.json` to locate the quoted
passages.


